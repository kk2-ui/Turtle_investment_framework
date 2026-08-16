# Phase 10 历史研究回测试点

状态：`PILOT_PREREGISTERED / ELIGIBLE_SET_EMPTY`

本试点用于工程验证并为后续校准收集诊断证据，不用于调参、挑选赢家或解锁 G3。它评价三件不同的事，三者不能互相抵消：

1. **报告覆盖度**：截至模拟日，重要主张是否有当时可见的官方证据，未知是否被保留。
2. **模型预测误差**：报告冻结的正常盈利、现金流、终值或经营阈值，后来实际结果偏离多少。
3. **投资结果**：按预注册的可执行价格、分红、税费、汇率、公司行动和基准计算的总股东回报。

## 历史信息边界

每个来源必须同时记录经济期间 `data_as_of` 和市场可见时间 `published_at`。两者都不能晚于模拟截止日。只有原始历史版本，或在截止日前已经披露的重述，才可进入冻结报告；当前数据库的修订值不能倒灌到过去。

冻结报告后，结算资料才可以打开。未来披露按真实发布时间走步进入，不能先读完整结果再补写预测。报告快照中的输入也禁止出现 `actual`、`outcome`、`realized_return` 等结算字段。

实验还必须预注册幸存者处理：后来退市、被收购或失败的公司不能从登记样本中删除。当前九份候选没有历史版本，仍然是资格不足，而不是被当作“未发生”。

当前试点明确登记为 `UNCONTROLLED / EXPLORATORY / ENGINEERING_DIAGNOSTIC_ONLY`：模型可能在训练中见过发行人及其后续事件，尚无可验证的参数记忆隔离证据。`MITIGATED` 必须有缓解证据且至多为 `QUALIFIED`；未来只有带部署级 attestation 的 `CONTROLLED` 才可能标为 `STRICT` 和模型记忆受控的校准候选。后者仍须通过独立的跨发行人、跨 cutoff 与 holdout 门槛，不能直接改参数或产生生产结论。

## 冻结报告与独立审阅

`FROZEN` 不是只有 JSON 或账本：它必须指向仓库内可读取的 Markdown 报告，包含 `report_id`、全部冻结 claim statement 和规定章节，并由 `COMPLETE` writer 提交。报告内容派生 `variant_id`，再确定性绑定 `freeze_id` 和 `HBTREV:<variant_id>` review identity；报告变化必须产生新 variant、新 freeze 和新审阅，旧结算不能借用新版本。`TEST_FIXTURE` 只允许 `HBTCASE:TEST` 回归命名空间。真实 case 的目标生产路径是 `PRODUCTION_PIPELINE`，将绑定 `scripts/turtle_agent/run.py` 输出、Phase 08 acceptance baseline、V3 gates、`publication_snapshot.json`、`run_manifest.json` 和 PIT runner attestation；P10-A 的 source-package runner/read audit 尚未实现，因此 validator 现在**故意拒绝**任何生产 case 为 `REVIEWABLE`，不会把任意 Markdown 或本地 JSON 当成真实历史报告。独立 reviewer 的身份与 context 不得和 writer 相同，并须声明未参与生成、上下文隔离和生成者身份不重叠；reviewer 所见的 SHA-256 必须与报告一致。reviewer 必须对每一个 claim 复核同一组冻结 `source_ids`；冻结为 `UNKNOWN` 的 claim 只能标为 `UNKNOWN_PRESERVED`，材料 `PREDICTION` 只能标为 `SUPPORTED`。结算的 `REPORT_COVERAGE` 逐项重放这份审阅，不能自行填写支持数、未支持数或未知保留状态。

当前冻结保证的 assurance level 是 `VERIFIED_ARTIFACT_AND_DECLARED_PROCESS`：它核对工件、管线入口、声明的 reviewer 独立性和版本身份，不是密码学作者证明，也不是模型没有历史记忆的证明。非测试 `CONTROLLED / STRICT` 需要部署级 attestation；该能力尚未实现，因而当前只能是 `UNCONTROLLED / EXPLORATORY / ENGINEERING_DIAGNOSTIC_ONLY`。未来 `MODEL_MEMORY_CONTROLLED_CANDIDATE` 仍须跨发行人、跨 cutoff 和 holdout 复验。

未通过时保留 `FROZEN_WITH_QUALITY_FAILURE` 和 `DATA_COVERAGE`、`ACQUISITION_MODULE`、`REASONING`、`MODEL`、`WRITING` 中的适用根因、经济影响、缺失事实、禁止假设、修复和验收条件。`tests/fixtures/historical_backtest_frozen_report.md` 只是 validator 回归夹具，不是任何历史公司的报告或回测样本。

## 冻结校准账本

每个可结算 case 在冻结时都必须写入 `calibration_ledger.claims`。它只记录会改变当时投资判断的材料性主张，不能用报告全文或事后叙事替代。每条主张必须：

- 绑定冻结来源清单中的 `source_ids`；输入的 `source_ids` 也必须在同一清单中存在；
- 明确标注为定量 `PREDICTION` 或 `UNKNOWN`；
- 对预测预注册指标、数值、期限和失效阈值；对未知项预注册经济影响和后续如何观察；
- 写出最强反方、结论翻转条件和后续可观察的结果口径。

冻结 case 不得出现 `actual`、`actual_value`、`outcome` 或其他事后结算字段。特别是不能在结算时把模型的原始数值改成后来更合理的数值：结算中的 `forecast_value` 必须逐字匹配对应冻结预测的 `value`，否则校验失败。

结算使用独立的 `actual_sources`，每一项实际现金流、经营观察和预测误差都要引用该清单中的来源。结算来源必须是官方来源类型，并记录 `published_at` 和 `source_version`；发布时间必须在模拟截止日之后、结算日之前。这样“事实后来发生了什么”与“冻结时报告主张了什么”可以逐项对照，但仍与覆盖度和投资结果分开保存。

### 经营预测结算契约

`calibration_ledger` 的每条 claim 只能对应一个经营观察口径。`observable_outcome` 必须冻结以下字段：

- `metric`、`unit`：指标和单位；
- `measurement_basis`：会计/经济口径，例如经营现金减维护资本、普通股归属和分母定义；
- `measurement_rule`：从年报或公告中如何计算该指标；
- `period_start`、`period_end`：要结算的经营期间，不能只写“下一年”；
- `allowed_source_types`：允许的后续来源，限定为 `ANNUAL_REPORT`、`INTERIM_REPORT` 或
  `EXCHANGE_ANNOUNCEMENT` 的明确子集。

`PREDICTION` 还必须冻结数值、方向、期限和失效阈值；预测及阈值的 `metric`/`unit` 必须与
`observable_outcome` 一致。`UNKNOWN` 不得伪造数值或阈值，但仍必须给出同样的指标、口径、期间和
允许来源，让后续年报可以结算“仍未知”或“未知已解决”。一个 claim 如果要观察两个不同指标，
必须拆成两个 claim，避免结算时把同名指标或不同会计口径混在一起。

后续 `actual_outcomes.operating_observations` 必须有唯一的 `observation_id`，并逐字匹配冻结
claim 的指标、单位、`measurement_basis` 和报告期。每个观测的来源类型必须属于冻结的
`allowed_source_types`；年报/中报来源还必须以 `data_as_of` 对应该观测的 `period_end`。
`model_forecast_error.metrics` 通过 `observation_id` 引用同一观测，实际值和来源清单也必须
一致。任何指标、口径、期间、来源类型或来源报告期漂移都会使结算 `INVALID`，而不是被平均分数
或收益结果掩盖。

## 回报通道与价格身份

报告必须先识别通道：

- `LONG_TERM_OWNER`：主要价格为 `P_LONG`，不要求市场在固定期限重新定价；有限期限退出只能作为辅助压力测试。
- `FINITE_XIRR`：主要价格为 `P_XIRR` 或 `P_LEGAL`，期限必须与资产、法律现金流或投资论点相匹配。
- `DUAL`：分别保存长期和有限期限路径；若主路线证据不足，主价格必须为 `UNKNOWN`，不能取平均。

由当前股价和任意“市场确认比例”推导的固定终值只能作为条件情景。没有独立终值证据时，不得成为主要行动价格。

## 当前九份候选试点

试点登记文件为 `config/historical_backtest_pilot.v1.json`。九份当前候选均被明确登记为 `INELIGIBLE_NO_HISTORICAL_VINTAGE`：现有候选保存的是最新研究输出，没有同时保存可验证的历史报告版本、逐源发布时间、当时市场数据和公司行动账本。因此当前**合格案例数为 0**，这不是回测失败，也不是对个股结论的否定，而是诚实的数据覆盖结论。

在取得历史年报原始版本、交易所发布时间、历史价格/分红/公司行动以及未幸存者样本，并完成 PIT runner/read audit 后，才可以把某个案例改为 `ELIGIBLE`。这只表示可建立来源齐备的工程 case；`calibration_eligible` 是单独计数，未来只有部署级 attestation 支持的 `CONTROLLED / STRICT / MODEL_MEMORY_CONTROLLED_CANDIDATE` 才可能进入后续样本与 holdout 审查。用户临时指定的公司必须保留 `USER_SELECTED_CASE` 标签，不能用于无偏总体胜率声明。

目前没有一个实际 historical case、冻结报告、走步结算或收益样本；试点的零合格案例和回归夹具都不能改变这一事实。

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
