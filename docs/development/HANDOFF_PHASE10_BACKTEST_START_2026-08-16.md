# Phase 10 历史回测启动交接

> 日期：2026-08-16（Asia/Shanghai）  
> 状态：`STARTED / FIRST_CASE_ACQUISITION_PENDING`  
> 交接范围：黄金候选的当前状态、已合入的回测基础设施，以及下一会话的执行顺序。

当前执行路线以 [Phase 10 回测路线图与模型行为契约](PHASE10_BACKTEST_ROADMAP.md) 和
[收益与选股评估契约](PHASE10_RETURN_SELECTION_EVALUATION.md) 为准；本交接只保留当时的启动状态。

## 1. 当前结论

可以开始历史回测的**资料采集、冻结案例和工程验收**，但不能把当前工作称为
“已证明有效的回测”或“已校准的报告标准”。

历史回测的三本账必须独立保存，不能合成总分：

1. `REPORT_COVERAGE`：冻结时材料性事实是否由当时可见的官方来源支持，未知是否被保留。
2. `MODEL_FORECAST_ERROR`：冻结的经营、现金、债务、阈值或价格前提与后续可观察事实的偏差。
3. `INVESTMENT_RETURN_OUTCOME`：按预注册执行规则、公司行动、税费和币种处理后的可执行回报。

当前九份黄金候选没有可验证的历史版本、逐源发布时间和当时市场数据，故全部仍为
`INELIGIBLE_NO_HISTORICAL_VINTAGE`。不得把今天的候选报告倒灌成历史回测样本。

## 2. 主线状态

- G2 跨报告裁决已完成；G3 仍为 `NOT_READY`；正式 Golden 报告为 `0`。
- `ACCEPT_WITH_DATA_LIMITED` 只表示特定范围的模型/内容审阅通过，绝不等于正式 Golden。
- 行业知识库已合入 `main`，用于提出跨公司取证问题，不能提供公司事实、估值参数、概率、价格或动作。
- 用户已明确授权开始回测基础设施与历史案例工作；这不解除黄金候选的 G3 门禁。

## 3. 九份候选的现行边界

详细真源：

- `docs/development/golden_set_v1/REGISTRY.md`
- `docs/development/golden_set_v1/CROSS_CASE_ADJUDICATION.md`

概览：

| 公司 | 当前状态 | 关键边界 |
|---|---|---|
| 汇贤 87001 | `ACCEPT_WITH_DATA_LIMITED` | `P_LEGAL=RMB0.1643`；BOP 台账、实体现金可达性、重庆签约租金和25%现金税/泄漏包络仍未闭合。 |
| 鄂尔多斯B 900936 | `ACCEPT_WITH_DATA_LIMITED` | 长期约9.01%、五年约9.21%；普通股现金可达性、税惠、维护资本、q、永煤分派性质和汇率仍受限。 |
| 格力 000651 | `ACCEPT_WITH_DATA_LIMITED` | `P_LONG=RMB33.47`；毛利/费用长期桥、资本开支、金融资产收益与留存用途仍要验证。 |
| 京投 01522 | `OBSERVE / NOT_GOLDEN` | 无新市场确认五年约8.17%、行动价约HKD0.196；有限确认价不能成为主价格。 |
| 中海物业 02669 | `ACCEPT_WITH_DATA_LIMITED`，非正式 Golden | 读者证据锚点独立通过；仍为 `PRIMARY_ROUTE_UNKNOWN`，行动价必须为 `UNKNOWN`。 |
| 中国食品 00506 | `ACCEPT_WITH_DATA_LIMITED` | 长期所有者通道为主；产品成本/费用、维护资本、现金归属和q仍受限。 |
| 天津发展 00882 | `ACCEPT_WITH_DATA_LIMITED` | 现金上游、NCI、维护投入和主路线未闭合；不得签发主要价格。 |
| 海螺 600585 | `ACCEPT_WITH_DATA_LIMITED` | 周期正常化、维护资本、可达性和供需退出仍受限。 |
| 紫金 601899 | `ACCEPT_WITH_DATA_LIMITED` | 逐矿成本/寿命、海外上游、联营现金、替代资本与长期主路线仍受限。 |

关键共同规则：业务驱动必须生成正常盈利，并继续传播至普通股现金、主要回报和主要研究价格；固定市场终值反解只能是条件价格；`UNKNOWN` 不得被保守归零或叙事掩盖。

## 4. 已合入的回测基础设施

`main` 当前基线为 `74f2bfd`。以下三项已合入并通过完整项目门禁：

1. `f59197e feat: add vintage-safe historical backtest pilot`
   - 建立试点、路线/价格身份约束和三账本分离。
2. `cb43849 feat: harden historical backtest vintage rules`
   - 每个来源要求 `source_version`；预注册并保留退市、收购和失败样本。
3. `74f2bfd feat: add frozen backtest calibration ledger`
   - 冻结 case 必须登记材料性预测、阈值或 `UNKNOWN`；输入的 `source_ids` 必须可解析到冻结来源。
   - 结算端必须引用独立、事后、官方来源；不得事后修改冻结预测值。

主要文件：

- `config/historical_backtest_pilot.v1.json`
- `docs/development/HISTORICAL_BACKTEST_PILOT.md`
- `schemas/historical_backtest_experiment.schema.json`
- `schemas/historical_backtest_case.schema.json`
- `schemas/historical_backtest_settlement.schema.json`
- `scripts/historical_backtest.py`
- `tests/test_stage36_historical_backtest_pilot.py`

上一次完整验证：`593 passed`。不要为了本次启动重复做哈希、校验和、全文存储或向量库。

## 5. 首个历史工程案例

提案文件：`docs/development/HISTORICAL_BACKTEST_FIRST_CASE_PROPOSAL.md`

| 项目 | 已预注册内容 |
|---|---|
| 公司 | 华夏幸福 `600340.SH` |
| 冻结截止 | `2020-04-27 18:00 Asia/Shanghai` |
| 执行规则 | 冻结报告后首个可交易日，原始未复权开盘价；具体交易日须由原始行情文件确认。 |
| 性质 | `PURPOSEFUL_STRESS_CASE`，仅用于工程/质量门验证，不计入总体胜率或参数校准。 |
| 路线 | `DUAL`；冻结前允许 `PRIMARY_ROUTE_UNKNOWN / UNKNOWN`。 |
| 观察窗口 | 一年与三年；不得宣称法律终局或五年回报已结算。 |

冻结日前的官方来源提案已经列明：2019 原始年报、2018 原始年报、2017 年报修订版、2017 年报问询与回复，以及2018-01-01至2020-04-27的上交所公告全集。2017 原始年报必须被截止日前已发布的修订版取代。2020 年一季报及之后的资料、2021 年债务事件、今天的重述数据库字段均不得进入冻结目录。

## 6. 下一会话的执行顺序

### A. 先完成首案的受控采集

1. 新建一个独立 worktree，从**本地当前 `main`**起步。主工作区目前与 `origin/main` 有分叉，不要先 `pull`、`reset` 或覆盖本地集成提交。
2. 用上交所一手链接/公告页面采集 600340 在 cutoff 前的文件；每份资料写入 `source_id`、`source_version`、`published_at`、`data_as_of`、`revision_policy` 与准入裁决。
3. 采集器必须能拒绝 cutoff 之后的来源和已被截止日前修订版替代的原版本。不要只下载选定年报，公告清单必须按日期和标题全量枚举，再按规则筛选。
4. 原始未复权行情、公司行动和沪深300基准各自建立来源账本；无法核对则让投资结果保持 `INCOMPLETE`，不阻断报告覆盖与模型误差结算。
5. 在冻结报告提交独立审阅前，禁止打开任何 cutoff 后的公告、报告、债务事件或行情结局。

### B. 冻结而不是事后补写

case 的 `calibration_ledger.claims` 至少覆盖：项目销售/回款与资本占用、受限现金、债务期限、担保/关联方资金占用、普通股可得现金、融资阈值、最强反方、永久损失触发条件。每一项必须写明：

- 支持来源和普通股经济影响；
- 定量预测及失效阈值，或明确 `UNKNOWN`、经济影响和后续解决观察；
- 反方论点、结论翻转条件和将来可观察口径。

冻结 case 若内容不足，状态应为 `FROZEN_WITH_QUALITY_FAILURE`，保留失败版本，不允许看过后来资料后重写成通过版。

### C. 再建立可校准样本集

首批六个工程 case-vintages 只验证证据包、冻结、走步结算、公司行动与路线差异。完整标准校准至少需要24个 case-vintages：六类经济机制各四例、每类至少两家发行人和两个不同 cutoff。对任何通用定量默认值的变更，需要至少10个已结算观察、三家发行人和两个 cutoff，再用12个未参与设计的 case-vintages 复验。

不得用单个好/坏投资结果修改 `q`、资本化率、10%目标回报或安全边际。

## 7. 已暂停的工作区

为交接而暂停，均无未提交改动：

- `feat/phase10-600340-precutoff-acquisition`
- `docs/phase10-sampling-protocol`
- `docs/phase10-freeze-contract-review`

可继续复用其中任一工作区；若新会话要独立推进，优先从当前 `main` 建立新 worktree，避免并行分支交叉污染。

## 8. 持续约束

- 一手公开披露是研究真源；用户个人假设不得作为证据、模型输入或正方催化剂。
- 港股现金分派税默认10%；本首案为A股，不应机械套用港股税率。
- 不增加哈希、校验和、向量库或全文存储，除非有明确用途并改变下一步决策。
- 发现材料性缺口时，按 `DATA_COVERAGE`、`ACQUISITION_MODULE`、`REASONING`、`MODEL`、`WRITING` 归因；先修可复用采集器/schema/validator，再重写报告。
- 每次写入使用隔离 worktree，提交后运行 `.venv/bin/python scripts/project_guard.py verify full` 和 `merge-check`；不要直接在 `main` 提交。
