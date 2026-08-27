# Round 10 V2 结果前独立复审回执

复审对象：`42e6ec6`（`fix(training): deduplicate round10 treatment delta`）。

## 结论

**PASS — 仅限 V2 treatment-delta 计数修复。**

三家公司可以分别留下同一处理变化的应用记录，但它们不再各自获得一次方法优势计数。`treatment_delta_ledger` 在批次级只登记
`R10:DELTA:ISSUER_CASH_NOT_OWNER_CASH` 一次；即使三家同时触发，`method_advantage_count` 仍为 `1`。

## 复核范围与结果

- 逐公司记录现为 `treatment_delta_application_id` 与 `treatment_delta_ref`，没有逐行的 `method_advantage_count`。
- 批次级 ledger 是唯一的计数位置；外部审阅验证器会拒绝重复 delta、非 0/1 的计数或批次合计大于 1 的对象。
- 新回归以三家均合格的合成结算输入确认：三条 application、一个 delta、计数为 1。
- `pytest -q tests/test_enterprise_judgment_round10_appliance_v2.py`：`6 passed`。

本复审未打开 FY2019 或其他结果期资料、价格、回报、H2、R-103、CJO 或报告材料；未访问网络。合成标签只用于验证计数不随公司应用次数累加，不代表任何真实结算。

## 仍然适用的边界

这项修复只防止同一方法变化被重复计功。它不确认方法具有材料投资效用，也不授予方法迁移、CJO、估值、报告、BuyBand 或投资权限。真实结果结算后仍须由外部独立审阅者按既有规则判断材料性处理变化或避免的方向性错误。
