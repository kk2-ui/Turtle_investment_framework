# Phase 10 历史研究回测试点

状态：`PILOT_PREREGISTERED / ELIGIBLE_SET_EMPTY`

本试点用于校准报告标准，不用于调参、挑选赢家或解锁 G3。它评价三件不同的事，三者不能互相抵消：

1. **报告覆盖度**：截至模拟日，重要主张是否有当时可见的官方证据，未知是否被保留。
2. **模型预测误差**：报告冻结的正常盈利、现金流、终值或经营阈值，后来实际结果偏离多少。
3. **投资结果**：按预注册的可执行价格、分红、税费、汇率、公司行动和基准计算的总股东回报。

## 历史信息边界

每个来源必须同时记录经济期间 `data_as_of` 和市场可见时间 `published_at`。两者都不能晚于模拟截止日。只有原始历史版本，或在截止日前已经披露的重述，才可进入冻结报告；当前数据库的修订值不能倒灌到过去。

冻结报告后，结算资料才可以打开。未来披露按真实发布时间走步进入，不能先读完整结果再补写预测。报告快照中的输入也禁止出现 `actual`、`outcome`、`realized_return` 等结算字段。

实验还必须预注册幸存者处理：后来退市、被收购或失败的公司不能从登记样本中删除。当前九份候选没有历史版本，仍然是资格不足，而不是被当作“未发生”。

模型记忆无法完全控制，因此即使文件围栏通过，也只能将大模型回放标记为 `QUALIFIED` 或 `EXPLORATORY`，不能冒充严格前瞻样本。

## 冻结校准账本

每个可结算 case 在冻结时都必须写入 `calibration_ledger.claims`。它只记录会改变当时投资判断的材料性主张，不能用报告全文或事后叙事替代。每条主张必须：

- 绑定冻结来源清单中的 `source_ids`；输入的 `source_ids` 也必须在同一清单中存在；
- 明确标注为定量 `PREDICTION` 或 `UNKNOWN`；
- 对预测预注册指标、数值、期限和失效阈值；对未知项预注册经济影响和后续如何观察；
- 写出最强反方、结论翻转条件和后续可观察的结果口径。

冻结 case 不得出现 `actual`、`actual_value`、`outcome` 或其他事后结算字段。特别是不能在结算时把模型的原始数值改成后来更合理的数值：结算中的 `forecast_value` 必须逐字匹配对应冻结预测的 `value`，否则校验失败。

结算使用独立的 `actual_sources`，每一项实际现金流、经营观察和预测误差都要引用该清单中的来源。结算来源必须是官方来源类型，并记录 `published_at` 和 `source_version`；发布时间必须在模拟截止日之后、结算日之前。这样“事实后来发生了什么”与“冻结时报告主张了什么”可以逐项对照，但仍与覆盖度和投资结果分开保存。

## 回报通道与价格身份

报告必须先识别通道：

- `LONG_TERM_OWNER`：主要价格为 `P_LONG`，不要求市场在固定期限重新定价；有限期限退出只能作为辅助压力测试。
- `FINITE_XIRR`：主要价格为 `P_XIRR` 或 `P_LEGAL`，期限必须与资产、法律现金流或投资论点相匹配。
- `DUAL`：分别保存长期和有限期限路径；若主路线证据不足，主价格必须为 `UNKNOWN`，不能取平均。

由当前股价和任意“市场确认比例”推导的固定终值只能作为条件情景。没有独立终值证据时，不得成为主要行动价格。

## 当前九份候选试点

试点登记文件为 `config/historical_backtest_pilot.v1.json`。九份当前候选均被明确登记为 `INELIGIBLE_NO_HISTORICAL_VINTAGE`：现有候选保存的是最新研究输出，没有同时保存可验证的历史报告版本、逐源发布时间、当时市场数据和公司行动账本。因此当前**合格案例数为 0**，这不是回测失败，也不是对个股结论的否定，而是诚实的数据覆盖结论。

在取得历史年报原始版本、交易所发布时间、历史价格/分红/公司行动以及未幸存者样本后，才可以把某个案例改为 `ELIGIBLE`。用户临时指定的公司必须保留 `USER_SELECTED_CASE` 标签，不能用于无偏总体胜率声明。

## 使用

```bash
python scripts/historical_backtest.py pilot \
  --output config/historical_backtest_pilot.v1.json
python scripts/historical_backtest.py validate experiment \
  config/historical_backtest_pilot.v1.json

# settlement 与冻结 case 一起校验，才能检查主张引用和预测值未被改写
python scripts/historical_backtest.py validate settlement \
  settlement.json --case frozen_case.json
```

完整对象约束见：

- `schemas/historical_backtest_experiment.schema.json`
- `schemas/historical_backtest_case.schema.json`
- `schemas/historical_backtest_settlement.schema.json`

本试点不修改任何个股模型、报告结论或 Golden Set 状态；`G3_NOT_READY` 保持不变。
