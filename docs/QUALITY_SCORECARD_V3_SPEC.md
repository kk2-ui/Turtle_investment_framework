# Turtle V3 投资研究质量契约

> 状态：Phase A 冻结；Phase B 已实现决策一致性硬门；Phase C 已实现重大主张—证据支持关系硬门。
>
> 实现真源：`scripts/decision_ledger.py`、`scripts/claim_evidence.py`、`scripts/evidence_citation.py`、`scripts/report_completion.py`
>
> Schema：`schemas/decision_ledger.schema.json`、`schemas/claim_evidence.schema.json`、`schemas/competitive_explanation.schema.json`

## 1. 目标

V3 不再把“研究执行、证据、推理、估值决策、表达”混成一个可互相抵消的总分。发布资格由顺序门控决定；展示分只能用于人工审阅排序。

```text
数据与身份
→ 关键事实及跨章口径通过？否则 INVALID
→ 重大主张闭环？否则 INCOMPLETE
→ 估值模型和动作一致？否则 INVALID/INCOMPLETE
→ REVIEWABLE / DECISION_READY
→ 发布后 MONITORING
```

## 2. 状态机

| 状态 | 精确定义 | 是否允许正式发布 |
|---|---|---:|
| `INVALID` | 已发现事实、身份、口径、模型或动作的关键矛盾 | 否 |
| `INCOMPLETE` | 未发现关键矛盾，但必要事实、主张链、指标或绑定尚未闭环 | 否 |
| `REVIEWABLE` | 硬错误已消除，允许人工研究员审阅，但 ledger 尚未冻结 | 否 |
| `DECISION_READY` | 关键身份、估值、风险和动作闭环且 ledger 已冻结 | 是 |
| `MONITORING` | 已发布，进入预测和触发器跟踪 | 是 |

V2 的 A/B/C/D 软雷达保留为诊断器，不决定上述状态。

## 3. 四层不可抵消成绩单

1. 数据真实性与身份：关键失败直接 `INVALID`。
2. 推理有效性：重大链条缺失为 `INCOMPLETE`；明显自相矛盾为 `INVALID`。
3. 估值与决策：模型、参数或动作冲突直接 `INVALID`。
4. 表达质量：连续评分或 WARN，不能抵消前三层失败。

展示模块可沿用 15/20/15/15/15/10/5/5 的建议权重，但任何加权结果都不能把 `INVALID` 或 `INCOMPLETE` 提升为可发布状态。

## 4. Decision ledger 是唯一决策真源

### 4.1 首批 canonical metric IDs

```text
market.price.current
return.gg.base
return.gg.fcfe
return.gg.normalized
hurdle.ii
valuation.v_final
moat.lambda
return.required
moat.decay
margin.price
margin.return
decision.position.recommended
trigger.buy
trigger.reduce
trigger.exit
```

每一个 active entry 必须声明：

- `entry_id`：正文引用的稳定身份；
- `metric_id`：上表 canonical 指标；
- `value` 与 `unit`；
- `scenario`：如 base/bear/bull；
- `basis`：计算口径；
- `as_of`：价格或信息日期；
- `version`；
- `status=active|deprecated`；
- `chapters`：该值应出现的章节；
- `source_ids`；
- `affects_action`。

正文使用：

```text
V_final 为 49.68 元/股。[decision: valuation.v_final@base.current]
```

### 4.2 允许与禁止的多值

允许共存：

- scenario 不同；
- as_of 不同；
- basis 不同；
- 旧值 `status=deprecated`，且有 `deprecation_reason` 和 `superseded_by`。

禁止共存：

- 同一 `metric_id + scenario + basis + as_of` 出现多个 active entry；
- 同一身份出现不同值但无上述解释；
- deprecated entry 仍被正文引用；
- 正文的 decision value 与 entry 不一致；
- ledger 的决策或仓位与 `decision_manifest.json` 不一致；
- frozen fingerprint 被直接修改。

禁止项产生 `INVALID`，不允许由软分或其他章节抵消。

### 4.3 缺失与未绑定

新 unified run 会写 `decision_ledger_policy.json` 并开启强制模式。以下情况为 `INCOMPLETE`：

- 缺 `decision_ledger.json`；
- 缺规定 canonical metric；
- entry 缺来源；
- ledger 声明某章使用该值，但对应章没有 `[decision: entry_id]`；
- 正文出现可识别的关键参数，却没有绑定相同 metric 的 decision ID；
- `decision_ready` ledger 未冻结。

旧输出目录既无 policy 也无 ledger 时返回 `SKIP`，避免迁移前存量报告被误杀；一旦存在 ledger，即使没有 policy 也会验证其真实性。

## 5. 冻结和 decision diff

首次写入生成：

- `decision_ledger.json`；
- `decision_diff.json`，状态 `INITIALIZED`。

冻结后的相同内容可幂等写入，diff 为 `NO_CHANGE`。冻结后的任何变化默认拒绝，原 ledger 不被覆盖，`decision_diff.json` 记录 `REJECTED_FROZEN`、变更前后、影响章节和是否改变动作。

局部 repair 不得调用 `write_decision_ledger` 或 `write_decision_manifest`。即使绕过 Agent 调度直接调用工具，frozen fingerprint 仍阻止静默漂移。未来真正授权 thesis/动作变更时，必须进入单独的 decision revision 工作流并提供 change reason；Phase B 不向 LLM 暴露解除冻结参数。

## 6. 完成契约映射

`report_completion.py` 的 V3 映射：

- ledger `INVALID` → completion `INVALID`；
- ledger `INCOMPLETE` → completion `INCOMPLETE`；
- ledger `DECISION_READY/MONITORING` → 继续其他完成门；
- ledger `SKIP` → 仅兼容存量目录；
- 其他结构/深度/审计硬失败仍为 `BLOCKED`。

组装器只发布 `COMPLETE` 或 `COMPLETE_WITH_WARNINGS`，所以三类失败都不能产生正式报告。

## 7. 主张—证据契约（Phase C 已实现）

重大主张必须结构化为：

```text
主张 → 原始事实 → 中间推理 → 最强替代解释
→ 适用条件 → 概率身份/置信度 → 对估值、仓位和动作的影响
```

来源不是简单“有/无”，而是二维身份：

- 权威性：审计财报、公司公告、官方统计、行业数据、媒体、其他；
- 与主张距离：原始数据、直接陈述、二次整理、分析判断、传闻。

每个重大主张以稳定 `[claim: claim_id]` 绑定正文，并登记在 `claim_evidence.json`。新 unified run 先写 `claim_evidence_policy.json`；缺账本、缺必需章节、缺直接支持、缺推理/适用条件/竞争解释/决策影响或正文绑定时为 `INCOMPLETE`。

每条 evidence 同时记录 `source_id` 与 `source_group_id`、`authority × claim_distance`、`published_at`、`data_as_of`、直接支持关系、口径匹配和利益冲突。同一原始来源的转载只算一个独立组。

未知来源、正文引用未知 claim、直接支持却口径 mismatch、用 `report_internal/report_derivation/framework_method` 自我循环支持，均为 `INVALID`。冻结账本只能幂等写入；漂移写入被拒绝并生成 `claim_evidence_diff.json`。

证据锚点还执行三条底层规则：复合来源逐组件解析；没有数字断言时邻证覆盖为 `N/A`；Markdown 表格可用紧邻的 `[table-source: X]` 映射整表，并进入验证、来源清单和脚注。

## 8. 竞争性解释契约（Phase E schema 已冻结）

核心 thesis 至少一条完整竞争性解释，包括：

1. 最强替代解释；
2. 支持它的证据；
3. 区分两种解释的观察；
4. 可获得时间；
5. thesis 翻转条件及依据；
6. 翻转后估值和仓位。

不再通过统计“但、然而”判断反证质量。

## 9. 估值、阈值和概率的后续硬化边界

Phase D 必须增加模型适用性、名义/实际、税前/税后、股权/企业价值、`r-g` 安全距离、终值依赖、多模型独立性和动作翻转测试。

Phase E 的阈值质量为：

```text
可观测性 × 依据充分性 × 区分能力 × 动作映射清晰度
```

无历史波动、同行基准或模型敏感性依据的精确阈值标记为伪精确。概率必须区分频率、基准率、分析师主观判断和情景权重。

## 10. 历史参考与后验校准

历史全文覆盖下降最终只应 WARN；只有已验证核心事实/证据无解释丢失才 FAIL。删除旧结论并记录 decision diff 属正常修订，不能被相似度机制阻止。本变更排在 Phase F，当前 `legacy_reference_regression.py` 行为暂不在 Phase B 扩大修改范围。

发布后分别记录过程校准和决策校准；不得用短期股价涨跌直接替代研究质量，也不得忽略预测和触发器的后验表现。

## 11. Phase B+C 验收

- schema 合法/非法 fixture；
- 无解释冲突为 `INVALID`；
- 不同 scenario/date/basis 合法；
- deprecated 值不污染 active 动作；
- manifest/ledger/Ch0/Ch14 一致；
- frozen ledger 拒绝局部漂移并留下 diff；
- 新 unified run 缺 ledger 为 `INCOMPLETE`；
- 旧报告无 policy 时兼容；
- V2 定向回归不得退化；
- 复合来源中任一未知组件必须失败；
- 直接支持不得来自报告内部循环，口径 mismatch 不得伪装成支持；
- 同源转载不得冒充多源交叉验证；
- 无数字断言为 N/A，表格级来源覆盖整表；
- 新 unified run 缺 claim ledger 为 `INCOMPLETE`；
- frozen claim ledger 拒绝局部漂移。

## 12. 当前可复现基线

Stage 1–5、9–12、自动修复与完成契约定向回归：`130 passed in 2.97s`。这是定向基线，不代表全仓测试全绿。

下一阶段为 Phase D：模型适用性与脆弱性硬门。必须覆盖 DDM/DCF/EPV/资产价值适用条件，股权/企业价值与税前/税后、名义/实际口径，`r-g` 安全距离、终值依赖、敏感性翻转、多模型共享假设，以及估值输出与仓位/动作的一致映射。不得回退到“公式数量越多得分越高”。
