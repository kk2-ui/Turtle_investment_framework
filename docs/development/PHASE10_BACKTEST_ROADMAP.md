# Phase 10 回测路线图与模型行为契约

> 日期：2026-08-16（Asia/Shanghai）  
> 状态：`ACTIVE / CONTRACT_FIRST`  
> 目的：用历史时点证据和可执行结果改进黄金报告，而不是用审计工件替代报告。

配套细则：[收益与选股评估契约](PHASE10_RETURN_SELECTION_EVALUATION.md)。该文定义完整候选宇宙、
执行、公司行动、基准和留出集；本路线图定义模型应遵守的顺序和阶段出口。
经营预测按年报/公告真实发布时间走步结算的细则见[经营预测与年报走步结算设计](PHASE10_OPERATING_FORECAST_SETTLEMENT.md)。

## 1. 用户目标

Phase 10 只服务两条需要分开回答的主线：

1. **报告标准是否进步**：在当时可见资料下，报告能否识别决定性事实、保留未知、建立正确的现金/债务/普通股价值桥，并把经营判断传播到价格和动作。
2. **推荐是否产生可执行收益**：在预注册的买入、持有、退出、税费、公司行动和基准规则下，黄金报告的推荐后来产生了什么回报、回撤和永久损失。

回测结果不得自动证明报告“正确”。报告质量、模型预测误差和投资结果必须分别保存；收益只能成为改进买点和选股的证据之一。

## 2. 不能再发生的失败

历史黄金报告工作曾把大量时间花在 hash、指纹和审计工件上，却没有先产出一份完整报告。Phase 10 的硬约束是：

- `FROZEN` 必须包含仓库内可读取的 Markdown 报告（`report_id`、全部 frozen claim statement 和固定章节）、`COMPLETE` writer，以及不同于 writer 的独立 reviewer；内容派生 `variant_id -> freeze_id -> review_id` 生命周期，报告变更必须新 variant、新 freeze、新审阅。生产适配器通过 `scripts/turtle_agent/run.py --pit-production-freeze` 绑定 PIT reads、Phase 08 acceptance/V3 gates、`publication_snapshot.json`、`run_manifest.json` 及 PIT runner attestation；只有 attestation 明确为 `PIT_PRODUCTION_FREEZE` 并可回放最终报告、来源锚点和实际读取时，production origin 才解除工具边界阻断。`TEST_FIXTURE` 只允许测试命名空间。reviewer 必须逐 claim 复核相同的 `source_ids`，并将冻结的 `UNKNOWN` 标为 `UNKNOWN_PRESERVED`。没有报告不得开始评分和结算。
- 未达到上述门槛只能是 `FROZEN_WITH_QUALITY_FAILURE`：保留分类、经济影响、缺失事实、禁止假设、可执行修复和验收条件，不能在看过未来资料后重写成通过版。
- hash、指纹和校验只在能跳过昂贵重读、或正式验收确实需要时使用；本阶段仅用冻结报告、模型控制证据和统一管线 variant 的 artifact SHA-256 发现内容变更并触发重审。它们不是研究产品、质量分数或回测结论。当前 assurance 是 `VERIFIED_ARTIFACT_AND_DECLARED_PROCESS`，不声称密码学作者独立性或模型记忆隔离。
- 资料不足时保留 `UNKNOWN`，不得把未知保守归零、补成漂亮假设或用审计循环掩盖缺口。
- 运行失败必须留下可恢复的失败工件和下一步，不能通过重复审计、换一套指纹或改写旧输入来制造 PASS。
- 任何后续事实、价格、重述或债务事件都不得倒灌到冻结报告。

## 3. 三本账与一条受控改进桥

### 3.1 `REPORT_COVERAGE`

冻结时记录并在独立审阅后逐 claim 回放结算，而不是让 writer 自报聚合计数：

- 材料性事实的官方来源覆盖率和来源版本正确性；
- `UNKNOWN` 是否被保留，未来信息是否泄漏；
- 业务驱动 → 正常盈利 → owner cash → 价值/回报/价格的传播是否闭合；
- 现金可达性、债务期限、担保、少数股东和维护资本是否遗漏或重复；
- 主路线、价格身份、动作和翻转条件是否一致；
- 是否实际生成完整报告，以及失败是否被诚实标记。

### 3.2 `MODEL_FORECAST_ERROR`

冻结时记录并在后续年报/公告按经营观察契约结算：

- 经营预测或 `UNKNOWN` 是否登记了指标、会计/经济口径、经营期间、失效阈值和允许的官方来源；
- operating observation 是否逐项匹配指标、单位、报告期、测量基础和允许来源类型；
- 预测值、阈值、经营变化和最强反方是否形成可复算的偏差或保留 `UNKNOWN`；
- 结算只能追加后续事实，不能改写冻结预测，也不能用股票收益替代经营判断。

### 3.3 `INVESTMENT_RETURN_OUTCOME`

只在报告冻结并通过独立质量审阅后结算：

- 预注册的首个可交易日、原始未复权价格和持有期；
- 现金分派、税费、交易费用、汇率、停牌、退市、收购、重组和其他公司行动；
- 个股总股东回报、回撤、永久损失状态和相对沪深 300/适用基准的结果；
- `INCOMPLETE` 的原因。缺失行情或公司行动只阻断相应收益栏，不得抹掉报告质量和模型误差结算。

### 3.4 `DECISION_IMPROVEMENT`

只有在三本账积累了足够、跨发行人和跨 cutoff 的样本后，才允许改变模型行为：

- 买点：比较报告当日执行、`P_LONG/P_XIRR/P_LEGAL` 身份及预注册的等待/分层进入规则；记录等待造成的机会成本，不能事后挑最低价。
- 选股：建立同一 cutoff 的候选池、未选控制样本和失败样本，比较风险调整后收益、回撤和永久损失，不只展示赢家。
- 规则修改必须先在设计集提出，再用未参与设计的 holdout 复验；单个好/坏结果不得修改 `q`、资本化率、目标回报率或安全边际。
- 改进同时要求 `REPORT_COVERAGE` 不退化。收益变好但事实覆盖、模型一致性或永久损失识别变差，不得合入。

## 4. 模型运行顺序（行为契约）

每个历史 case 必须严格按以下顺序运行：

```text
预注册 cutoff/样本/执行规则
  → 受控采集截止日前资料
  → 生成完整冻结报告和 claim/forecast/UNKNOWN 账本
  → 独立质量审阅
  → 锁定冻结输入
  → 打开 cutoff 后官方资料并走步结算
  → 分开结算报告质量、模型误差、投资结果
  → 仅在 holdout 通过后提出模型/买点/选股修改
```

模型在每一步的行为要求：

1. 报告 writer 以冻结资料为唯一输入；未来结算资料在工具层不可读。
2. 任何材料性主张都必须有 `source_ids`、预测值或 `UNKNOWN`、失效阈值、最强反方和可观察口径。
3. 主价格身份未知时输出 `UNKNOWN`，不得用市场反解价格、平均值或保守归零替代。
4. 资料不足仍要完成报告结构；无法达到质量门时输出失败状态和具体缺口，而不是只输出 schema/hash 通过。
5. reviewer 只能审已经存在的报告和结构化账本，逐 claim 复核 disposition 与来源；不能先用评分结果指导 writer 重写冻结输入。
6. 结算器只能追加实际来源和结果，不能修改冻结预测值；`forecast_value` 必须逐字匹配冻结值。
7. 任何模型更新都必须给出变更原因、设计集、holdout、未改善维度和回滚条件；没有证据时保持现行规则。

## 5. 阶段出口

### P10-A：契约和受控采集

- 预注册实验、cutoff、来源版本、执行规则和幸存者处理；
- `ELIGIBLE` 只表示历史来源可建立 case；`calibration_eligible` 单独计数，只有模型记忆受控的候选才可能进入后续 holdout 审查；
- 采集器按公告日期全量枚举，拒绝 cutoff 后来源和截止日前已被修订版替代的原版本；
- `scripts/phase10_pit_runner.py` 已实现 source-package allowlist、只读 PIT runner 和读取审计，并由 production origin 回放 source identity、cutoff、package root 和实际 ALLOW 事件；框架读取根目录固定为仓库内受控静态目录，并在 attestation 记录 root 与 `REPOSITORY_STATIC` provenance。它不使用来源内容 hash。准入 PDF 必须同时保留原始 `package_path` 和来源包内 `PDF_PAGE_MARKDOWN` 页码文本表示；少任一项即为 `INCOMPLETE`，不能把 base64 当作可读年报证据；
- `scripts/turtle_agent/run.py` 现区分 `--pit-preflight` 和 `--pit-writer`：两者都拒绝复用 output、跳过普通 Phase 0-2/网络/当前行情准备，且 output 必须与历史来源包和静态 framework 根目录隔离。writer 只注册 `pit_list_sources`、`pit_read_source`、`pit_read_framework` 和无路径参数的 `pit_write_report`；它不加载普通 contract、旧输出、tracking、数据库、Web 或价格。任何未提供的工具入口（包括 Web、普通 Turtle 输出读取和年糕上下文）都会以 `TOOL / DENY` 写入同一 read audit；写入时逐一核对正文 source anchor 对应本运行实际 ALLOW 的 source_id，最终 attestation 回写真实 read audit 和 writer outcome；
- 草案 writer 仍只生成受限 Markdown，不能取代生产冻结。独立的 `--pit-production-freeze` 入口只提供 PIT 读取、无路径 V3 写入器、实际读取后的文档投影、事实核验后的确定性 V3 前置刷新、完成/快照/run-id 复核和独立 Phase 10 acceptance root；它不开放 Web、行情、数据库、普通输出读取或任意路径。尚未完成独立 reviewer 和完整 case lifecycle 的真实案例仍为 `INCOMPLETE`；
- 首案 600340 形成可审阅的冻结来源包。

**出口**：来源准入测试通过，且没有任何未来文件可被冻结运行读取。

### P10-B：首份历史报告

- 从冻结来源包生成一份完整报告；
- P10-B writer boundary 已实现：真实 LLM 仅可通过 PIT allowlist 读取来源与框架，并只能向新沙箱写一份 Markdown 草案。该草案明确保留 `UNKNOWN`，禁止收益、买点、选股、仓位和事后结论；它是完整生产冻结报告的输入，不是替代品；
- 至少覆盖项目销售/回款与资本占用、受限现金、债务期限、担保/关联方占用、普通股可得现金、融资阈值、最强反方和永久损失触发条件；
- 每项可量化经营判断必须在冻结时登记指标、单位、目标期间、可比口径和后续年报结算规则；无法如此定义的内容必须是有经济影响的 `UNKNOWN`；
- `FROZEN` 必须有 repo-relative Markdown artifact、固定章节和 claim statement、匹配的 artifact SHA-256、`COMPLETE` writer、声明隔离的独立 reviewer 和所有 claim 的逐项审阅；`UNKNOWN` 只能为 `UNKNOWN_PRESERVED`，材料预测必须为 `SUPPORTED`。否则保留带完整根因的 `FROZEN_WITH_QUALITY_FAILURE`。

**出口**：存在完整报告及可逐项结算的 calibration ledger；没有“只有 hash、没有报告”的交付。

### P10-C：走步结算和收益账

- 只在冻结后打开后续公告和行情；
- 分开结算 `REPORT_COVERAGE`、`MODEL_FORECAST_ERROR`、`INVESTMENT_RETURN_OUTCOME`；
- `REPORT_COVERAGE` 从冻结时独立 reviewer 的逐 claim 记录回放；支持、部分支持、未支持和未知保留不能由聚合数字替代。`MODEL_FORECAST_ERROR` 只从冻结 claim 的经营观察契约结算：观测必须匹配 `metric`、`measurement_basis`、报告期、单位和允许来源类型；未知项可以保持 `UNKNOWN`，不能用收益栏替代；
- 后续年报、半年报和公告严格按 `published_at` 走步；版本修订、未披露和口径漂移追加展示，不能静默覆盖已结算观察或强行产生误差；
- settlement 必须绑定冻结的动作、价格身份和执行规则，并具备可复算的成交、公司行动、税费、逐笔现金流和基准账本；
- 停牌、退市、重组、未核对公司行动保持 `INCOMPLETE`，不得机械归零。

**出口**：至少一个 case 完成三账分栏，或明确记录每一栏的缺失原因。

### P10-D：跨 case 质量与选股评估

- 首批工程 case 只验证工程链路，不用于胜率或参数校准；
- 目标样本至少 24 个 case-vintages：六类经济机制各四例，每类至少两家发行人和两个 cutoff；
- 设计集与 holdout 分离，保留未选控制和失败样本。

**出口**：能回答“报告标准改善了什么”和“推荐相对基准是否改善”，而非只给平均收益。

### P10-E：受控改进

- 通用定量默认值的修改至少需要 10 个已结算观察、三家发行人、两个 cutoff，并用 12 个未参与设计的 case-vintages 复验；
- 买点和选股规则的改动必须同时通过质量不退化门和收益/永久损失门；
- 未满足样本门时只记录研究假设，不修改生产模型。

## 6. 外部能力的吸收边界

| 外部能力 | 可复用部分 | 明确拒绝 |
|---|---|---|
| `daily_stock_analysis` | 评估窗口、方向/持仓映射、止盈止损事件、结果状态和汇总接口 | 其文本建议映射不是 Turtle 价格身份；不提供 PIT 证据围栏、完整公司行动账或总股东回报真源 |
| `ai-berkshire` | 事件触发 + 基本面验证的诊断思路、买点候选比较 | 手工基本面、赢家示例、当前数据回填和单股长持收益不能作为校准证据 |
| `AlphaEvo`/同类策略工程 | 参数探索和组合实验的工程参考 | 不允许直接优化 Turtle 的估值、目标回报率或动作规则，不共享 canonical 账本 |
| `QuantConnect/Lean` | 成交、费用、滑点和组合路径的可替换 sidecar | 不读取或改写 Turtle 冻结报告；不能替代来源、判断或估值审阅 |

## 7. 当前状态和下一步

- 当前九份黄金候选仍是 `INELIGIBLE_NO_HISTORICAL_VINTAGE`；不能用今天的报告倒灌历史回测。
- G3 仍为 `NOT_READY`；首案 600340 是 `PURPOSEFUL_STRESS_CASE`，不代表总体成功率。
- 600340 已完成 P10-A 的 cutoff 前 source package，并在未打开后续资料前生成 PIT engineering draft。该 draft 的正式状态是 `FROZEN_WITH_QUALITY_FAILURE`；新的 production adapter 不会回填或升级它。v1 仍缺完整报告章节、可冻结的经营预测、估值、价格、行动和独立 reviewer，故只能证明工程边界，不是通过的历史报告。
- 该诊断已建立一份 2020-04-28 至 2021-04-27 的官方 SSE 公告元数据库存和按 claim 的待读计划；元数据不等于后续经营事实，尚未读取公告正文、行情、公司行动或沪深 300。三账当前为 `REPORT_COVERAGE=PASS`（仅回放冻结时的 UNKNOWN 审阅）、`MODEL_FORECAST_ERROR=NOT_CALCULABLE`、`INVESTMENT_RETURN_OUTCOME=NOT_CALCULABLE`，没有收益、买点或选股结果。
- 当前 case 的 lifecycle identity 已是规范 `HBT:`，但它显式保留 legacy `HBTEXP:` writer attestation，因此仍要求用规范 identity 新建 production freeze。后继 `historical-backtest-*.v2` 已把经营观察的真实 `measurement_period` 与公告 `observation_window` 拆开，并要求 actual observation 只能使用 `BODY_READ` 官方来源；不得静默修改这个质量失败 case。下一步是以 v2 新 case 在 production adapter 中重新冻结并完成独立 reviewer，随后才可按元数据待读计划逐份打开官方正文；无冻结动作和价格身份时，仍不得采集行情或计算收益。
- 当前试点的模型记忆状态固定为 `UNCONTROLLED / EXPLORATORY / ENGINEERING_DIAGNOSTIC_ONLY`。未来只有部署级 attestation 支持的 `CONTROLLED / STRICT` case 才可能是模型记忆受控的校准候选；当前 validator 未开放该路径，这仍不替代跨发行人、跨 cutoff 和 holdout 门槛。
- 只有生产 case 完成 P10-B 后，才允许进入可校准的 P10-C；只有多个 production case 完成 P10-C 后，才讨论买点、选股和模型更新。

这份路线图的验收标准是“先有可读、可审、可结算的完整报告，再有回测结论”。任何只增加 hash、指纹、分数或审计文件而没有改善报告和可执行结果的改动，不算 Phase 10 进展。
