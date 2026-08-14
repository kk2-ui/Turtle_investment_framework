# Turtle Investment Framework 长期开发路线图

> 状态：ACTIVE ｜ 建立日期：2026-08-02 ｜ 最近更新：2026-08-14 ｜ 当前主阶段：Phase 08（VALIDATING）
>
> 本文件是项目开发状态、优先级和阶段依赖的唯一索引。方法公式以对应规范为准；历史过程不再写入交接文档。

## 1. 长期目标

把 Turtle 从“自动生成投资报告”建设成“自动获取可复核证据、选择决定性问题、采用适用估值模型、形成一致决策并接受后验检验”的价值投资研究系统。

成功不以报告更长、公式更多或软评分更高定义，而以以下结果定义：

1. 重大事实可追溯至原始文件、页码或表格位置。
2. 每家公司只优先研究真正影响价值和动作的少数问题。
3. 模型与公司类型匹配，脆弱假设和动作翻转条件可见。
4. 数字、估值、仓位和触发器由同一结构化真源生成。
5. 发布后的预测、阈值和决策能够被长期校准。
6. 操作人审阅的是完整报告是否符合其投资体系及最终结论，而不是逐项审批研究过程中的临时动作。

### 1.1 用户重申的最终目标

本项目的目标不是生成更短、更容易通过评分或盲评的报告，也不是把研究过程变成需要操作人逐步批准的工作流。目标是建立一个能够在取得充分上下文后，自动完成完整价值投资研究并给出最终判断的系统；操作人最终判断的是成稿是否符合其投资体系、是否偏离其思路，而不是代替Agent审阅全部中间步骤。

完整报告应当把从格雷厄姆到巴菲特的思想连成一条主线，而不是选择其中一部分：

1. 从格雷厄姆出发，先看资产负债表、现金与负债、盈利能力、可验证的资产价值和安全边际。
2. 走向巴菲特时，继续判断商业模式、护城河、管理层与资本配置、留存利润的再投资回报、长期所有者收益及价值如何向小股东兑现。
3. 现金存在、法律归属、母公司可分配能力、实际分红回购和额外现金兑现是不同层次。可达性尚未完全验证不等于现金价值为零；已经发生的普通分红、回购、利息收入和母公司储备必须进入判断，尚未验证的额外部分应以折价、区间和条件表达。
4. 分析必须服从企业自身属性。央企、地方国企、民企、金融企业、周期企业和轻资产服务企业具有不同的存续风险、治理约束、资本配置路径与适用估值方法；企业标签只能改变证据权重，不能替代事实。
5. 不同估值方法回答不同问题。资产价值、盈利能力价值、股东回报买入线、成长价值和清算压力情景应分别解释，不能为了得到一个漂亮数字而强制收敛或机械平均。
6. 最终动作必须由要求回报、安全边际、经营质量、现金兑现和反方证据共同决定。价格便宜不能自动抵消兑现不足，好公司也不能自动证明当前价格值得买。
7. 报告是完整研究产品。摘要用于帮助阅读，不得替代商业、行业、护城河、财务、治理、现金、风险、估值、反方和执行逻辑的完整分析；改进可靠性不应以丢失有效上下文和研究信息为代价。
8. Agent应在完整上下文、证据、估值、竞争解释和全文一致性闭环后自动形成结论。只有最终结论及其与投资体系的关系需要呈现给操作人，正常报告不设置逐章、逐模型或逐候选动作审批。

所有阶段目标、质量门、盲评和工程优化都服务于上述目标。若阶段指标与完整价值投资研究发生冲突，应修正阶段实现，而不是改变最终报告的产品目标。

## 2. 不可妥协原则

- **质量优先**：节省 token 不得以减少原始资料阅读、推导或反证为代价。
- **自动运行**：新能力必须进入统一管线，不能只对单只报告人工打补丁。
- **原始证据优先**：交易所、公司公告和审计财报优先于媒体、搜索摘要和内部推导。
- **未知就是未知**：未找到资料不得推断为规模很小、风险很低或已经定价。
- **硬门不可抵消**：事实、口径、模型或动作失败不能被表达质量和总分抵消。
- **结构化真源**：关键参数和动作只允许存在一个 canonical identity。
- **阶段完成主义**：一次至少完成一个可验收阶段；同一时间只推进一个主阶段。
- **不为指标写作**：字符数、因果词和公式数量只用于发现空壳，不是研究深度目标。
- **完整报告后置裁决**：估值、论点或洞见阶段出现的Buy/Hold/Avoid只能是内部工作假设；在全文、反证、触发器和一致性门闭环前，不得向操作人请求动作审批，也不得冒充最终投资结论。
- **体系审阅而非过程审批**：人工界面只呈现投资哲学一致性、关键偏离、最终结论及其翻转条件。内部模型选择、参数修订和章节传播由系统自动完成并接受机器审计。

## 3. 当前基线

截至2026-08-02，已经具备：

- 确定性财务计算、PDF预处理、Zone B/Zone J和15章自动报告。
- Decision、claim evidence、valuation model、thesis test和insight结构化账本。
- 估值模型适用性、竞争解释、阈值概率和跨章一致性硬门。
- 独立判断审阅、最多三项定向研究、fresh-context续跑和独立综合挑战者。
- 可用来源身份、空搜索识别、PDF/网页读取游标和不可变发布快照。
- validation-only与失败码传播，失败报告不能伪装成正式成功。
- 决定性问题引擎在写作前确定性选择最多三项，强制竞争解释、区分信号、有界研究、淘汰理由和估值/仓位翻转路径。
- 入选问题必须提交研究结论；未闭环、伪造观察身份或无证据提高置信度会阻断发布，insight不得另造问题。
- 版本化公司原型与估值路由在写作前自动固化，账本不能绕开模型角色、现金流/价值口径、折现率类型、独立性和禁用模型理由。
- 130家公司资料的364个文件已建立可追溯机制索引，明确禁止作为当前公司事实或直接复制参数。
- 决策编译器在组装前从冻结账本生成Ch0、Ch9、Ch12–Ch14受保护区块；自由旧值、区块篡改、动作矛盾和未批准decision diff均阻断。
- 追加式基准率案例库按机制检索、冻结as-of-time证据并阻断未来信息泄漏；少于5个独立合格案例时禁止输出经验概率。
- 格力、分众和中海物业已形成9个真实候选case，覆盖3个原型和4类机制；当前0个`ELIGIBLE`，不会把候选或130家公司估值索引冒充历史结果。
- 发布后监控计划自动冻结阈值、预测期限和案例任务；新披露以来源哈希追加，自动形成事实差异、阈值窗口判断和待复核决策差异，禁止自动交易。
- 校准面板分开显示过程、预测、触发器和决策结果，并强制展示样本量；金融街物业FY2024→FY2025真实披露演练已通过但不冒充前瞻成绩。
- 安全运行层已统一模型能力下限、预算、重试、超时、限流、内容寻址缓存、运行manifest、脱敏、保留预览和恢复建议；关键任务不得静默降级或接受截断输出。
- 用户批准的本地密钥文件保持原位且被版本控制隔离，实际边界审计未发现运行产物泄漏。
- 当前主干阶段回归基线：`403 passed`；全仓测试另受可选`tushare`依赖和嵌套旧仓库测试命名冲突影响，不得宣称全仓全绿。
- Phase 08首个A股真实候选（格力Phase08）已以validation-only进入`READY_FOR_BLIND_REVIEW`，全程未发布；下一机器验收出口是港股候选通过相同硬门，而不是继续修改格力单例。
- 港股候选金融街物业已完成官方事实、派生计算、decisive plan观察集合和估值路由身份的保守迁移：70条官方`OBS:`与105条允许列表`CALC:`观察均可重建验证，claim账本为`DECISION_READY`；三个决定性问题的语义身份未变，decisive gate仅因findings未执行而`INCOMPLETE`。估值迁移已安全绑定EPV、DDM和RETURN_DECOMPOSITION并在candidate补记拒绝DCF_FCFF，但未把真实语义差异强制改名：EPV owner earnings定义、DDM独立组及RETURN_DECOMPOSITION角色/口径/required-return仍令valuation为`INVALID`。canonical估值、动作、仓位、decision ledger和decision diff均未改变；decision diff仍待人工批准，不得绕过。
- 最新迁移相关定向测试为`48 passed`，当前`tests/test_stage*.py`选择为`361 passed`。路线图此前记录的`403 passed`来自当时不同的阶段回归选择；两者均按实际命令保留，不互相冒充全仓测试。
- 首次valuation定向实跑在第9次调用暴露调度缺陷：结构化valuation仍未通过时，下游Ch0/Ch14质量提示错误开放了正文writer。运行在首次越界写章后立即中止，未提交估值账本、未发布；Ch14已从运行前快照恢复，canonical估值和两份决策文件哈希不变。结构化frontier现在优先于派生章节提示，未通过时强制`synthesis_only`；最新相关回归`115 passed`、阶段测试`363 passed`。按ADR-008，下一次valuation writer实跑需要重新批准，不得自动重试。
- 第二次获准run验证正文冻结有效，但暴露更深的估值防伪缺口：旧validator接受把六个semantic frontier字段机械改成route要求并宣称研究完成。该假通过已保存到`/tmp`后精确回滚，canonical估值恢复`d2da1439…09633`，决策和正文不变。新`valuation-semantic-research`门要求每项变更具有精确VERIFIED证据、机制和估值/动作影响，并禁止frontier外任何模型或synthesis变化；失败稿重放现被六项missing resolution阻断。thesis畸形嵌套参数也已从运行异常改为结构化INVALID。最新相关回归`103 passed`、阶段测试`367 passed`；valuation仍有意保持`INVALID`。

当前主要缺口不是基础门控，而是研究能力上限：

- 基准率案例库已可用，但尚无到期且独立复核的`ELIGIBLE`样本，后验统计仍需时间积累。
- 真正的前瞻监控样本尚未到期；无人值守调度与外部告警尚未启用，当前恢复与发布仍保留人工确认边界。
- Phase 06已完成不可变快照、追加事件、阈值与校准基础设施，但尚未把旧报告的决定性问题逐题结算，也未以机器硬门保证H1对H1、Q1对Q1、年报对年报，更未形成可加总复核的经营变化—干扰因素桥；这些能力进入Phase 09。
- 年糕Web已有分析历史和股票详情基础，但尚未消费Turtle监控事件、问题结算与可比期间变化；Phase 09将建立只读投影，Turtle结构化账本继续作为唯一审计真源。
- 当前行情职责已冻结：年糕负责provider、刷新和行情真值，Turtle只读消费带provider/fetched-at/batch/hash的快照。当前价变化必须穿透重算市值、收益率、安全边际和动作；冻结账本不得被行情刷新器直接覆盖，PIT回测不得接入当前行情。
- 行情刷新决策边界已进一步冻结：程序可确定性重算市场价、三种GG、价格/回报安全边际及综合回报买点；买点、仓位适用人群或买卖动作发生变化时，先生成指纹绑定的内部候选账本并自动完成全文传播。只有完整报告通过机器门后，才形成面向操作人的体系一致性/最终结论审阅；此前不得改canonical发布账本。报告层禁止复用`V_cash`模糊符号，分配价值、净现金和现金余额必须使用不同身份。
- 现有年糕`run_backtest`只是用历史报告价格锚与当前价格做启发式比较，Turtle historical replay也只验证监控链路；两者都不等于“仅使用历史时点可见信息重新生成报告”的point-in-time研究回测。严格历史信息围栏、走步结算、总股东回报和基准比较进入Phase 10。

## 4. 目标架构

```text
官方文件/审计财报/交易所公告
        ↓
文档身份与逐页证据平台
        ↓
已验证事实 + 显式未解决缺口
        ↓
决定性问题选择与研究优先级
        ↓
行业原型 + 估值模型路由
        ↓
主张/估值/论点/决策账本
        ↓
关键章节决策编译 + 技术报告解释
        ↓
不可补偿发布门
        ↓
完整报告的投资体系一致性审阅
        ↓
预测、触发器、实际结果与长期校准
```

搜索引擎只用于发现线索。网页摘要、内部章节和框架方法不得替代原始事实。

## 5. 阶段路线

| 阶段 | 功能 | 状态 | 依赖 | 核心出口 |
|---|---|---|---|---|
| 01 | [官方证据平台](stages/01_OFFICIAL_EVIDENCE_PLATFORM.md) | **COMPLETE** | 当前基线 | 可复核的文档、事实和report context |
| 02 | [决定性问题引擎](stages/02_DECISIVE_QUESTION_ENGINE.md) | **COMPLETE** | 01 | 1–3个价值敏感且可区分的问题 |
| 03 | [行业原型与估值路由](stages/03_INDUSTRY_ARCHETYPES_AND_VALUATION.md) | **COMPLETE** | 01、02 | 行业特定证据需求和模型组合 |
| 04 | [决策编译器](stages/04_DECISION_COMPILER.md) | **COMPLETE** | 02、03 | 账本单向生成关键章节和动作 |
| 05 | [基准率案例库](stages/05_BASE_RATE_CASE_LIBRARY.md) | **COMPLETE** | 01、02 | 当时可见事实与历史结果样本 |
| 06 | [监控与校准](stages/06_MONITORING_AND_CALIBRATION.md) | **COMPLETE** | 04、05 | 发布后自动更新和后验评价 |
| 07 | [模型编排与运行治理](stages/07_MODEL_ORCHESTRATION_AND_OPERATIONS.md) | **COMPLETE** | 贯穿；最终收口 | 安全、可控成本与可观测生产运行 |
| 08 | [真实报告验收与质量校准](stages/08_REAL_REPORT_ACCEPTANCE_AND_QUALITY_CALIBRATION.md) | **VALIDATING** | 01–07 | 盲评候选、黄金不变量与真实质量基线 |
| 09 | [纵向论点跟踪与年糕可视化](stages/09_LONGITUDINAL_THESIS_TRACKING_AND_NIANGAO.md) | **PLANNED** | 01、02、04、06、08 | 同期可比、逐题结算、干扰桥及Web历史时间轴 |
| 10 | [历史时点研究回测](stages/10_POINT_IN_TIME_RESEARCH_BACKTEST.md) | **PLANNED** | 01–09 | 无未来数据的历史报告、走步结算及决策质量评价 |

阶段状态只允许：`PLANNED → IN_PROGRESS → VALIDATING → COMPLETE`。无法继续时标记 `BLOCKED` 并写清唯一阻断条件；不得用“基本完成”代替出口验收。

### 5.1 外部能力候选的阶段路由

截至 2026-08-14，用户批准把以下开源项目纳入长期能力候选，但不授权整套替换现有系统：

| 候选 | 当前定位 | 最早准入阶段 | 与 Turtle 的边界 |
|---|---|---|---|
| [ai-berkshire](https://github.com/xbtlin/ai-berkshire) | 外部研究挑战器和问题库 | Phase 08 G2，G3 前完成 | 只比较方法覆盖和确定性小工具；输出不进入 canonical 证据、判断或动作 |
| [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis) | 行情/事件采集、调度与通知工程参考 | Phase 08 G4；事件接入最早 Phase 09 | 年糕仍拥有 provider 与行情真值；Turtle 只接收带 provenance 的快照，新闻线索须回到原始来源核验 |
| [FinceptTerminal](https://github.com/Fincept-Corporation/FinceptTerminal) | 综合终端产品参照 | Phase 09 产品设计 | 默认只参考通用需求；不复制代码、具体界面或 trade dress，不建立运行依赖 |
| [QuantConnect/Lean](https://github.com/QuantConnect/Lean) | 可替换的执行与收益结算 sidecar | Phase 10 | Turtle 先冻结历史信息集、报告和决策；Lean 只模拟成交、费用、滑点和组合路径 |

吸收顺序统一为：能力缺口审计 → 固定 revision 与许可证/数据条款审阅 → 最小隔离原型 → 与现有 schema 和真源边界对抗验证 → 独立审阅 → 才能进入统一管线。外部项目不得以受欢迎程度、功能数量或示例报告质量绕过 Golden Set、证据门和 Research Handoff 契约。

```text
ai-berkshire 挑战问题 ─→ Turtle G2 方法裁决
daily 事件/行情模式 ──→ 年糕市场真值与事件箱 ─→ Turtle 原始证据复核
Turtle PIT 冻结决策 ──→ Lean 执行结算 ─────────→ 年糕分栏展示
FinceptTerminal ───────→ 只提供产品需求参照
```

## 6. 全局完成定义

每一阶段只有同时满足以下条件才可标记 `COMPLETE`：

1. 运行时能力进入统一自动管线，不依赖人工拼报告。
2. 新接口有schema或等价机器契约，并有向后兼容策略。
3. 单元、对抗、集成测试通过，既有阶段回归不得退化。
4. 至少覆盖A股、港股和一种不同商业原型的真实样本。
5. validation-only先通过；正式发布测试不得覆盖旧快照。
6. 失败、缺失、截断和冲突路径都可观察且可恢复。
7. 阶段文档更新最终结果、偏差和剩余限制；不记录逐轮聊天流水账。

## 7. 真实样本篮子

| 标的 | 主要用途 |
|---|---|
| 01502 金融街物业 | 港股披露、关联方资金、治理和现金可得性 |
| 000651 格力电器 | A股、成熟消费、资本配置和多模型冲突 |
| 002027 分众传媒 | 轻资产特许经营、商誉、周期和成长价值 |
| 02669 中海物业 | 物业同行、弱护城河和正常化盈利 |
| 00506 中国食品 | 少数股东、AP融资和价值兑现 |

阶段不必每次跑完全部样本，但必须按风险选择至少三个，并保留一个未参与规则调试的控制样本。

## 8. 文档真源与历史资料

| 文档 | 角色 |
|---|---|
| 本路线图 | 唯一开发状态、顺序和阶段索引 |
| `QUALITY_SCORECARD_V3_SPEC.md` | V3质量与发布契约真源 |
| `REPORT_CONTEXT_DESIGN.md` | Phase 01设计输入，不代表当前实现状态 |
| `turtle_graham_deepening_roadmap.md` | Graham方法迁移和校准记录 |
| `value_investing_from_graham_to_buffett_notes.md` | 书籍研究资料 |
| `V12_MANUAL.md` | 现有运行手册，后续由Phase 07统一更新 |
| `HANDOFF_ACCOUNT_SWITCH_2026-08-02.md` | 历史交接快照，不再追加开发进度 |
| V2评分卡与早期migration/brief文档 | 历史设计依据，不是当前路线图 |

发生冲突时：运行代码和测试说明“现在做了什么”，对应schema/规范说明“必须做什么”，本路线图说明“接下来做什么”。

## 9. 阶段工作纪律

- 开始阶段前，把对应阶段文档从骨架补成决策完备实施规格。
- 实施期间只更新该阶段状态和必要设计决策，不写账号交接文档。
- 不在一个阶段顺手扩大到下一个阶段；发现的问题进入路线图backlog。
- 删除或迁移历史产物前先确认真源、引用和可恢复性。
- 质量规则需要真实标的校准；纯fixture通过不能宣称研究能力完成。
- 外部项目只能在第 5.1 节指定阶段启动；实现前必须记录固定 revision、许可证、数据条款、保留/拒绝能力和退出条件。

## 10. 近期顺序

1. 完成Phase 08真实validation-only样本：至少一个A股和一个港股通过机器硬门并进入盲评。
   - 估值层产生的动作变化只记录为`INTERNAL_SYNTHESIS_REQUIRED`，不得中途请求人工审批。系统须继续完成thesis、decisive findings、insight、Ch0/Ch14及全文传播，机器门通过后才向操作人呈现“投资体系是否一致 + 最终结论”。
   - 港股估值身份迁移工作包已完成。下一个最小工作包是有界定向估值研究：使用migration candidate和精确semantic frontier，验证owner earnings定义及RETURN_DECOMPOSITION应承担的模型角色；不得仅改字段名，不改既有估值值、动作、仓位或decision diff，除非新验证证据明确要求进入受审决策变更。
   - 首次定向run已发现并离线修复结构化frontier被Ch0/Ch14派生提示旁路的缺陷；下一断点仍为valuation writer，须以新的明确批准重启单context/12调用上限，不能因上次未完成而扩大预算。
- 第二次run已封住“机械改字段冒充语义研究”。下一次valuation writer必须逐项提交六条证据支持的semantic resolutions；仍需新的明确批准，且不得复用已否决的假通过账本。
- 第三次run验证了证据身份上下文：第二次提交已让六项resolution全部绑定VERIFIED证据且无越界模型变更，但required-return完整对象未在迁移任务旁明示，模型只填kind；四条“无变化”影响说明也被质量门正确拒绝。契约已补齐`value_pct/tax_basis/inflation_basis`精确伴随规则，空洞影响说明不降标。运行在第6次调用由同错熔断停止，canonical与正文均未变化。下一工作包仍是同一valuation writer，须重新批准一次有界实跑。
- 第四次run把validation收敛到0项INVALID、3项INCOMPLETE，但证明fresh context没有复用上一轮最佳拒绝稿，会重复构造并短暂回归。框架已加入同frontier、同source-ledger约束下的`rejected_research_resume`及最佳拒绝稿择优保留；恢复稿无权威且必须重新完整验证。阶段回归`369 passed`。下一断点仍是valuation writer，仅剩M003一条联合证据与两条非空影响链，须重新批准后实跑。
- 第五次run真实验证最佳稿不会被空稿/3行退化稿覆盖，同时暴露“提示只修3项、writer却要求重传全对象”的接口冲突。writer现支持受约束的`resume_best_rejected + semantic_resolution_patches`，只传修正行，由程序按frontier键合并并全量重验；不降低任何证据或越界保护。阶段回归`370 passed`。下一断点仍为同一valuation writer的3行补丁，须重新批准后实跑。
- 第六次run以3次调用真实通过补丁式writer；六项语义研究0 INVALID/0 INCOMPLETE，冻结后valuation为`DECISION_READY`，模型结果、synthesis、动作、仓位和decision diff均未变化。promotion同步语义凭证fingerprint的生命周期缺口也已修复。01502估值工作包关闭；下一依赖frontier为旧thesis的`resolution_due`及其candidate-first迁移，不再重跑valuation。
- 01502旧thesis唯一失败是PS001缺`resolution_due`；竞争解释、阈值、概率及动作均已通过。新增candidate-first截止日迁移，仅在预测as-of等于报告期末且无其他错误时，按下一可比披露期限确定性补齐；所有研究语义受保护，依赖SHA漂移即拒绝。实际零模型补为`2026-09-30`后thesis达到`DECISION_READY`，completion降为`INCOMPLETE`，阶段回归`375 passed`。下一frontier为3个decisive findings，不再重跑valuation/thesis。
- 3个decisive findings首轮有界实跑在2次完成调用后发现估值route迁移不幂等：兼容账本仍被重复promotion并触发plan输入刷新。运行按“首个新框架缺陷即停止”中止，未写findings、正文或决策。迁移现以剔除生命周期元数据后的主体判断是否需要执行；已兼容账本不再写入，误报semantic frontier的运行提示也已修正。连续复验中估值SHA及decisive输入fingerprint均稳定，阶段回归`376 passed`。下一frontier仍为3个findings，须获得新的明确付费批准后再跑。
- 第二轮有界实跑发现更上游的身份环：valuation routing把下游decisive plan纳入公司原型输入，plan又依赖archetype/route；同时routing把`report_context.meta.generated_at`视为事实变化。运行在2次完成调用后中止，未写findings或canonical研究产物。现已切断下游反向依赖，并让routing绑定证据平台稳定`context_fingerprint`；不同run ID下连续两次完整上游重建得到同一decisive fingerprint且零源差异。阶段回归`377 passed`，下一frontier仍为3个findings，须再次明确批准付费运行。
- 第三轮启动后decisive fingerprint保持稳定，身份链修复通过真实验证；但writer把空`findings: []`的`INCOMPLETE`对象写成canonical并返回`written=true`。运行在第2次完成调用后中止，空稿已转为last-attempt审计。persist现只允许`DECISION_READY`获得canonical身份，INVALID/INCOMPLETE均返回失败且不覆盖；工具schema同时禁止空数组。阶段回归`378 passed`。下一frontier仍为覆盖3个问题的完整findings，须再次明确批准付费运行。
- 第四轮生成3条完整finding并通过旧结构门，但人工证据审计发现DPS趋势写反、最高利息/最高余额被误算成年化利率、维持性Capex逻辑自相矛盾，以及大量无直接身份的数字与机制。decisive gate现要求全局OBS/CALC声明、逐signal `evidence_ids`和逐数字直接支持；解释、决策影响及结论也与证据和canonical账本核对。失败稿在新门下为15 INVALID/6 INCOMPLETE，已转为同fingerprint可恢复的非权威candidate。阶段回归`379 passed`，下一frontier是基于该稿删除错误推导并补逐信号证据，须再次明确批准付费运行。
- 第五轮复用候选并两次提交，但模型自造`CALC:compute_gg:gg_base=6.2`等可读ID、引用非allow-list `compute_ddm`和临时算式，硬门正确拒绝并由同错熔断在4次调用后停止。契约现把105条全量计算压缩成31条decisive相关精确哈希映射，明确CALC只能复制不透明ID；数字提取同时排除证据ID本身的哈希数字，防止假失败。阶段回归`381 passed`。下一frontier仍为同候选的精确CALC修订，须再次明确批准付费运行。
- 第六轮第一次大对象提交被拒后，第二次退化为空数组并覆盖last-attempt；canonical未受污染，但完整失败稿丢失。decisive writer现增加同fingerprint `best_rejected`，按缺失问题数→INVALID→INCOMPLETE择优，空稿不能覆盖3/3候选；last-attempt只做最新诊断，恢复优先best。对抗回归通过，阶段测试`382 passed`。本轮结束前尚无best文件，下一次需重建完整候选，之后研究进展不会再被退化稿覆盖；须再次明确批准付费运行。
- 第七轮已重建3/3候选，best-rejected在真实运行中成功保留，当前得分0 missing/13 INVALID/0 INCOMPLETE。离线修复规范值两位小数舍入和年报页码两项假失败后，其余均为真实无支持数字；validator现逐项返回`unsupported=...`，下一context可按13条精确缺数定点删除或补OBS/CALC。阶段回归`383 passed`，须再次明确批准付费运行。
- 第八轮候选在旧集合式数字门下表面通过，但独立审计发现CALC身份借用、金额与百分比直接比较、Capex逻辑矛盾、无证据绝对化和decision ID漏绑。框架已改为逐引用数字身份核对，增加量纲/绝对断言校准与active decision binding，并修复计算单位推断；该候选重验为16项INVALID且下游读取被关闭。阶段回归`453 passed`，下一frontier仍是同3个finding的补丁式语义修订，须重新批准付费运行。
- 第九轮前修复validator升级后的best重评，并为decisive writer加入同fingerprint字段补丁模式；真实8-call运行把旧门错误由16项降至9项但仍未通过。新失败显示模型会用“0搜索命中”冒充不存在证据，并用“无法解释/结构性驱动/真实可持续”等改写绕过绝对词表。框架现区分直接事实、`[inference]`和`[negative-evidence]`，后两者必须保留具体unresolved；新门下best为23项显式INVALID，canonical与下游仍关闭。阶段回归`458 passed`，下一frontier仍为该best稿的字段补丁，须重新批准付费运行。
- 第十轮通过`local_patch_no_new_research`恢复路由在4次调用内把旧门23项收敛至4项并由同错熔断停止；独立审计拒绝“贴上inference标签即视为有效”的漏洞。框架现要求`[inference:Ixxx]`逐项绑定结构化audit（证据、最强替代解释、区分观察、判断错误时的决策影响），且推断存在时confidence单次最多上调0.05。当前best按新门为13 INVALID/3 INCOMPLETE，均属本地字段迁移，无需新搜索；阶段回归`460 passed`，须重新批准后继续同一补丁frontier。
- 第十一次run在第3次调用使旧门首次DECISION_READY，但独立审计发现owner-return结论跳过计划中的折价GG 5.3%<II 5.5%，现金和经营问题也未结算各自sensitivity basis。框架新增逐前提`resolution_assessment`，A/B并存必须MIXED，未知关键前提不得RESOLVED；11个计划敏感值已获得稳定`decisive_plan` CALC身份。目标writer成功后控制流现在立即停点，不再扩张到insight。旧canonical按新门为0 INVALID/14 INCOMPLETE并转为最佳恢复稿，阶段回归`464 passed`；下一frontier仅补3个assessment，须重新批准。
- 第十二次run用3/4次调用完成目标writer并在同批次立即停点，49,107个未缓存输入token、零搜索、零provider重试。独立审计拒绝把31.8年分红覆盖解释成快速兑现，也拒绝用244.6%净现金/市值及市场折价循环证明现金受控。框架为每个前提新增诊断角色、允许方向和唯一`decisive_plan` CALC绑定；现金、owner-return和经营转折的已知标尺均有确定性方向约束，并让validator升级后的完整canonical自动成为非权威恢复frontier。真实稿按新门为6 INVALID/0 INCOMPLETE，均是本地方向或身份修补；五个核心账本/正文哈希不变，阶段回归`467 passed`。下一frontier只修这6项，不得搜索，须重新批准。
- 第十三次run用3次调用关闭旧6项，但独立审计发现新`resolution_assessment`未继承数字/引用/推断门。框架现对decision consistency及每条premise说明执行局部证据和推断审计；新门产生11项显式错误。第十四次run又用3次调用把其收敛到4个无身份临时差值并由同错熔断停止，两轮共130,293个未缓存输入token、零搜索、零provider重试。恢复writer现可安全接受patch或完整候选，避免严格工具schema造成一次无效大对象调用。best为4 INVALID/0 INCOMPLETE，五个核心哈希不变，阶段回归`470 passed`。操作人已授予持续付费授权，但每次仍须有界、先离线测试、成功即停、缺陷即熔断；下一frontier只删除或正式绑定4个临时差值。
- 下游预检已提前区分两类阻断：旧insight只缺决定性问题身份，待decisive通过后应做零模型确定性迁移；D014/D015的decision diff真实改变动作，必须保留人工批准，不得把“无需逐次批准模型费用”扩大成“自动批准投资动作”。
- 第十五批三次有界run共9次调用、185,443个未缓存输入token、零搜索：best从4项收敛到2项，并先后暴露完整重传越界修改、结构化frontier被派生Ch12/Ch14/Ch0抢占、validator路径与补丁schema不一致。框架已限制只改当前错误问题、让未完成结构化frontier绝对优先于章节、并提供安全`premise_resolution`别名；真实复验已确认直接进入decisive writer。旧insight的唯一问题身份已生成`READY_TO_PROMOTE`零模型候选，但仍受decisive正式通过门约束。核心哈希不变，阶段回归`474 passed`；下一frontier仅修operating的2个局部字段，不得搜索或重写正文。
- 第十六次3-call run证明别名仍被误实现为整数组替换：模型提交两条部分前提行后产生8 INVALID/2 INCOMPLETE，best保护使2项旧候选不退化。框架现改为按`premise_key`局部合并并拒绝未知/重复键，未提交的计划值、方向、证据及其他行均保持不变。该run为61,700个未缓存输入token、零搜索，阶段回归`475 passed`；下一次仍只允许关闭同2项，不扩展研究范围。
- 第十七次3-call run以68,970个未缓存输入token真实关闭decisive frontier，3个问题均为`DECISION_READY`且成功即停；insight问题身份随后零模型晋升为`DECISION_READY`，迁移记录的幂等`PROMOTED`状态也已补齐。当前机器硬门只剩`decision_diff_approval_pending`：D014/D015改变减仓/退出动作，必须人工批准或拒绝，不能用模型费用授权代替。报告仍未发布，阶段回归`475 passed`。
- 预批准临时副本演练发现动作diff尚未传播至所有旧正文，批准后仍会因3处“大股东减持直接退出”冲突和4个自由关键值变为INVALID。compiler现把manifest动作冲突与全文关键值检查前移到审批之前，并提供受限的manifest动作迁移和canonical摘要单向重写。01502已零模型修复3处旧动作、仓位、r*/decay绑定及退出条件，重验为0 INVALID、仅待人工diff批准；阶段回归`478 passed`。不得在此结果之前把审批视为机械签字。
- 操作人已明确批准D014/D015。批准后修复了decision ledger与compiler对负号decay/小数比例r*的等价语义、compiled source provenance、validation-only双层draft落盘、memo+technical组合variant，以及validation-only误覆盖tracking latest正式别名。零模型收口manifest为`COMPLETED / VALIDATED_NOT_PUBLISHED`；金融街物业以组合variant `45a455f8b3eeaafa`正式进入`READY_FOR_BLIND_REVIEW`，与格力Phase08共同完成A股+港股机器验收子目标。阶段回归`483 passed`；Phase 08仍保持VALIDATING，下一出口是独立盲评与冻结后控制样本，不得把机器通过提升为洞见优秀或正式发布。
- 独立盲评契约已升级至V2：评审必须绑定当前盲评包hash、记录独立context及actor/provider/model，并与run manifest汇总出的候选生成身份隔离；同名评审或复用同一context均不能凑票。01502已识别生成身份`deepseek_oa:deepseek-v4-pro`并生成V2模板，当前仍无有效盲评、状态不变。下一步只能由两个真正隔离且未参与生成的评审读取盲评包，主流程不得自评冒充独立票。
- 01502首轮双盲已完成：两份V2评审均有效且独立给出`FRAGILE`，共同识别`V_cash`同名异义，并指出市场价格时效、买入线与综合回报门不一致、λ/阈值缺校准等重大问题。状态机新增不可补偿`REVISION_REQUIRED`并结构化保留fatal findings，防止用更多评审票稀释失败；当前聚合为1 READY、1 REVISION_REQUIRED、1 TECHNICALLY_BLOCKED、1 NOT_ASSESSABLE，0 BENCHMARK_APPROVED，阶段回归`419 passed`。下一工作包按市场as-of→指标语义→动作门→参数校准→primary research硬门顺序修通用框架，再生成新variant复盲，控制样本继续留置。
- 首轮盲评前三类缺陷已升级为通用发布硬门：决策策略绑定市场价截止日与默认7天有效期；V_cash等canonical符号同名不同值直接失败；负回报安全边际下的买点必须显式满足综合回报门，未触发买点时正仓位必须限定既有持有人。01502零模型重验命中市场价过期216天、V_cash 605M/1,695M冲突及两项动作矛盾，completion降为INVALID；validation-only draft身份修复确保规则升级后仍保留原variant和双盲历史。阶段回归`424 passed`，当前聚合为1 READY、2 TECHNICALLY_BLOCKED、1 NOT_ASSESSABLE。下一步是自动修复路径和参数/primary research硬门，仍不打开控制样本。
   - valuation通过后才依次修复thesis、执行decisive findings和insight；不得提前实施Phase 09/10，也不得为赶进度自动批准decision diff。
2. 冻结规则后才打开中海物业控制样本；完成两份独立评审和一次人工指纹批准，形成首个黄金不变量。
3. 按披露周期积累真正前瞻的监控与校准样本，不用历史回放冒充预测成绩。
4. 实施Phase 09：先完成可比期间身份和问题结算账本，再完成干扰因素变化桥，最后把审计结果投影到年糕股票详情页；Web不得自行推导研究结论。
5. 实施Phase 10：以预注册的公司、历史cutoff和持有期运行当前统一框架，建立严格信息围栏；先做单公司工程验收，再做多公司、多起点走步回测，结果接入年糕但与真实前瞻成绩分栏。
6. 定期根据真实报告质量复核模型等级和任务预算；价格只在核验后显式更新。
7. 若引入无人值守调度或外部告警，另立阶段规范，保持自动发布和自动交易默认关闭。
8. 继续用真实失败案例扩充运行故障库，任何清理仍须预览、指纹确认并可恢复。

### 2026-08-04 当前检查点

- Phase 08仍按既定路线推进，没有进入Phase 09/10。01502经批准的年糕行情刷新已完成全依赖传播，并以0次模型调用通过真实validation-only入口；新variant `90d0830770a28cf6`为`READY_FOR_BLIND_REVIEW`。
- A股格力与港股金融街物业已同时满足机器验收子目标。旧01502盲评与新variant哈希不匹配，已自动失效；接下来是新variant双盲，而不是继续单报告增补或提前打开控制样本。
- 新variant若通过两份隔离评审，才冻结Phase 08规则并运行02669控制样本；控制样本和人工指纹批准通过后，Phase 08方可从`VALIDATING`转为`COMPLETE`。
- 新variant第二轮双盲已完成且两票均为`FRAGILE`，01502退回`REVISION_REQUIRED`，因此上条冻结条件没有满足。当前Phase 08唯一合法下一步是修复两名评审共同命中的结构性框架问题；不得打开02669，也不得提前实施Phase 09/10。
- 第三variant的通用可靠性主干已完成：现金法律可达桥、参数证据、模型可比性、联合压力、负安全边际动作门、equity/value-realization算术、synthesis到主模型对账以及决策变化的两阶段事务均已进入代码和对抗测试。真实运行证明结构frontier可压缩到4工具且不会静默覆盖canonical。
- 01502当前形成一个实时可验证的非canonical决策修订proposal，指纹`24d4b580…b29`：`Buy/3.5%/V=3.22`拟改为`Avoid/0%/V=1.9062926934`。候选decision reliability为`DECISION_READY`，结构只剩manifest action、position和D006冲突；completion应保持`PENDING_APPROVAL`，不得把整夜框架开发授权解释成该投资动作的批准。
- Phase 08尚未完成。严格剩余顺序是：人工批准或拒绝该指纹；若批准则原子传播decision ledger/manifest/valuation及下游章节；生成第三variant并取得两份隔离盲评；两票无fatal后冻结规则；最后打开02669控制样本并完成人工黄金指纹批准。任一环失败都回到Phase 08，不进入Phase 09/10。

### 2026-08-04 最新真源检查点（覆盖同日旧记录）

以下状态覆盖本路线图中同日所有“Buy/Avoid候选待批准”“PENDING_APPROVAL”或旧variant记录；旧段落只保留为研发历史，不再代表当前执行入口。

- 01502金融街物业已完成完整报告综合和零调用validation-only收口：completion=`COMPLETE`，manifest=`COMPLETED / VALIDATED_NOT_PUBLISHED`，当前机器状态=`READY_FOR_BLIND_REVIEW`。
- 当前报告variant为`806b7d884e741856`，blind packet SHA-256为`08bc62b26d96a9c7ca467c2fb7274350989c0a09834f74ab238e09cf5f39d782`；组装器已从稳定报告身份恢复公司名，简版和技术版标题不再为空。旧variant的四份盲评均已失效，当前有效独立评审为`0/2`。
- 最终综合结论为`Hold / Cautious Watch`，未持有人仓位`0%`。当前价`1.99 HKD`，经营EPV `3.148815 HKD/股`，价格安全边际约`36.8%`，股息率约`7.8%`，回报安全边际`-7.0pct`，观察区间`1.55 / 3.1488 / 4.52 HKD`。
- 价值路线按格雷厄姆到巴菲特的资产、盈利能力、成长和兑现拆分：经营EPV是主锚；未证明高回报再投资时不计成长溢价；额外现金因分配桥未闭合暂不计入基准，但作为潜在上行单列，绝不等同于价值为零。公司按官方资料识别为北京市西城区区属国企，而非央企。
- 内部proposal在完整manifest、decision ledger、估值、thesis、insight、触发器和报告语义一致后自动解析，不再插入操作人动作审批。正常报告生成保持自动；操作人审阅对象是成稿的投资体系一致性、偏离和最终结论。
- A股+港股真实统一管线机器子目标已经完成。Phase 08仍为`VALIDATING`的剩余原因仅是质量校准协议：先取得当前variant两份真正隔离的盲评；若无`FRAGILE`/fatal finding再冻结规则；之后才打开02669控制样本；最终只对首个黄金契约进行一次阶段级人工指纹批准。
- 黄金契约批准用于确认Phase 08 benchmark和规则，不是以后每份报告都要批准。当前没有需要操作人批准的01502动作，也没有继续付费修复该报告的必要。阶段测试最新为`489 passed`。

### 2026-08-04 第三轮深层修复完成（最新真源）

- 第三轮盲评命中的EPV正常化、价值到回报桥、触发器语义、伪增量ROIC和业务结构口径已转为通用框架硬门，不是单样本文字补丁。
- 01502经营EPV改为FY2023—FY2025税后OCF减Capex三年均值，归母正常化FCF `124.010367M RMB`，主锚 `2.9604679507 HKD/股`。当前价1.99的价格安全边际32.8%，五年无收敛/完全收敛/严重压力IRR分别约7.8%/15.0%/-1.3%，基准回报安全边际-2.2pct。结论保持`Cautious Watch / 0%`。
- 零修复轮validation-only达到`COMPLETE`，全阶段回归`503 passed`。新variant=`cb77a9de88918fe7`，blind packet SHA-256=`3b0754b6ae376ff89f44c452f2630c2464721a932b0f34d38c6702f99af8486b`，机器状态`READY_FOR_BLIND_REVIEW`。
- 旧评审因variant/hash不匹配全部失效，当前有效票`0/2`。下一边界是两个全新隔离评审actor，不是用户重新批准01502结论。在两票通过前不冻结规则、不打开02669、不进入Phase 09/10。

### 2026-08-04 两票COMPETENT后的第四候选

- variant `cb77a9de88918fe7`取得两份有效独立评审，均为`COMPETENT`且fatal finding为0。验收器没有因“无致命问题”自动授予黄金质量；升格仍要求至少一票`INSIGHTFUL`。
- 评审命中的客观口径漂移已清除：错误同行CAGR、办公楼/商务分部混用、税前/税后FCF混用、DPS趋势误述和6%/7%阈值冲突已修正；严重压力现在同时将盈利与股息减半，IRR为-6.1%。
- 新variant=`ae7c524e3a3a988f`，packet SHA-256=`90065985b066ef2674b4be14d6403d0be51a43be40a79c94f6501091b6392145`；completion仍为`COMPLETE`，阶段回归`503 passed`，当前有效票`0/2`。必须用两个新隔离actor复盲，不得复用刚完成的评审上下文。

### 2026-08-04 第二组COMPETENT与第五候选

- variant `ae7c524e3a3a988f`的两份全新隔离评审均通过独立性和hash校验，裁决均为`COMPETENT`且fatal finding为0。两票共同确认决定性现金问题与动作闭环较强，同时共同指出全文信息效率弱，因果/证据仍有超出披露颗粒度的归因。
- 报告已撤销第三方低毛利的项目级归因、员工成本“60%+”、三类可能重叠资金合计约9亿元及70%/20%/10%主观原因拆分；规模洞见降回“面积与收入同比例增长、单位利润下降”的可核验层。Ch11缩为历史GG诊断，当前回报仍由五年IRR桥裁决。
- 零修复轮validation-only为`COMPLETE`，全阶段回归`503 passed`。新variant=`4d425612a81c40cc`，packet SHA-256=`a93d09a52c5cc747fa6dabc07e0dd7e581100ebf48e37d1fd4c4283b994edcac`，机器状态`READY_FOR_BLIND_REVIEW`，有效当前票`0/2`。
- 下一出口仍是经操作人授权的两个全新隔离评审actor。没有`INSIGHTFUL`票前不冻结规则、不打开02669控制样本，也不降低质量门槛；该授权不是普通报告投资动作审批。

### 2026-08-04 第五候选双INSIGHTFUL与控制样本揭盲

- variant `4d425612a81c40cc`由两个全新隔离actor完成盲评，两份工件均通过variant、packet hash、身份和生成者隔离校验；裁决均为`INSIGHTFUL`，fatal finding为0。机器状态正式升为`BENCHMARK_CANDIDATE`。
- 达到预先冻结条件后，Phase 08验收规则已设为`rules_frozen=true`，不是因看到控制样本结果后再调规则。02669中海物业随后首次进入验收集合。
- 控制样本当前为`NOT_ASSESSABLE`，原因是旧目录缺少completion、runtime manifest和Phase 08结构化账本；这不是质量失败。真实运行预算预检上限约320次LLM调用、64分钟，要求显式`--approve-expensive-run`。
- 当前唯一合法停点是操作人批准或拒绝该控制样本运行预算。未批准前不绕过02669、不生成黄金契约；批准后按冻结规则运行，控制样本通过才进入最终一次黄金指纹人工批准。

### 2026-08-04 Phase 08最终批准检查点（历史检查点，已被下一节覆盖）

- 02669控制样本已经在冻结规则后通过：variant `347019c3e490c2e2`，两份独立盲评为`INSIGHTFUL + COMPETENT`，fatal finding为0，机器状态`BENCHMARK_CANDIDATE`。
- 控制样本的`Avoid / 0%`结论按格雷厄姆—巴菲特路线形成，普通分红和额外现金分层；2.42港元为10%要求回报买入线，当前3.44港元不满足回报安全边际。
- 真实盲评推动框架新增λ真实中位数和不可执行价格动作硬门；报告清除了AA双口径、EPV算术、价格止损、衰减重复扣减与不可复算NAV。
- 当前验收集合有两个`BENCHMARK_CANDIDATE`。Phase 08不再等待报告运行或普通投资结论批准，只等待首个黄金契约一次性人工指纹确认：`5e1e00ae0d28d058d0f08410592debcccc614016a0c551cc8dedac895e74a45a`。
- 指纹批准后重跑验收，01502应成为`BENCHMARK_APPROVED`，Phase 08方可标记`COMPLETE`并进入Phase 09；该批准不会成为普通报告逐份审批流程。

### 2026-08-05 完整报告目标校正检查点（历史检查点，已被下一节覆盖）

- 用户否决了把02669压缩备忘录及技术附录作为后续完整报告标准；上一节“只等待旧黄金指纹即可进入Phase 09”的判断已经失效，旧黄金预览和指纹暂停，不得确认或跨版本复用。
- Phase 08继续保持`VALIDATING`。机器`BENCHMARK_CANDIDATE`只说明旧验收器状态，不能覆盖用户对报告产品形态和信息完整性的否决。
- 当前唯一正确顺序为：恢复用户认可的高信息密度完整报告产品；迁移已验证的现金/兑现、AA、λ、要求回报和执行逻辑修复；重建compute、估值、论点、证据与决策结构化真源；由统一管线形成同一variant；重新运行机器验收和独立完整报告评审；最后生成新的黄金批准预览。
- 操作人最终审阅的是完整成稿是否符合其投资体系、是否偏离其思路以及最终结论是否成立。正常报告不设置逐章、逐模型或逐候选动作审批。
- 本检查点的详细事实、失效工件和执行顺序以`docs/HANDOFF_PHASE08_GOAL_REALIGNMENT_2026-08-05.md`为准。在新完整报告和新黄金预览完成前，不得把Phase 08标记`COMPLETE`，不得进入Phase 09实施。

### 2026-08-13 多黄金报告集合检查点（当前最新真源，覆盖旧单样本路线）

- 用户明确判定旧的“02669单样本校准 → 01502单holdout → 单黄金契约”路线覆盖面过窄。Phase 08 改为建立由多种公司形态和价值路线共同组成的 `Golden Set v1`。
- 当前指定案例为 02669、000651、00882、01522、600585、87001 和 900936；它们分别承担轻资产服务、成熟现金制造、综合控股、项目型科技、重资产周期、有限期限REIT和多实体周期制造的机制覆盖责任。
- 每份报告可以使用不同叙事顺序、章节标题、表格和适用模型；统一的是内容必答问题、普通股价值守恒、材料性质量门槛和独立接纳要求，不是机械统一格式。
- 当前阶段只审内容质量。可读性、长度、视觉和排版不阻断，除非会造成事实、估值、回报或永久损失判断错误。
- 正确顺序为：逐案内容成熟与接纳 → 跨报告裁决共同不变量和路线差异 → 冻结多报告 Golden Set v1 → 从集合反推统一流水线 → 两个全新 holdout 盲测 → Phase 08 收口。
- 旧 01502/02669 benchmark身份、旧黄金预览、旧评审票和旧Q1执行顺序均只作历史资料，不得自动沿用；01502因长期参与规则形成，不再具备真正holdout身份。
- 当前执行细节、候选成熟度、Agent工作顺序和完成定义以仓库根`GOALS.md`为准。G6完成以前不得进入Phase 09/10。

### 2026-08-14 外部能力候选检查点

- 用户批准把 `ai-berkshire`、`daily_stock_analysis`、`FinceptTerminal` 和 `QuantConnect/Lean` 纳入长期路线，但不改变当前 Phase 08 G1。
- G2 才进行 ai-berkshire 方法挑战，G4 才审计 daily 的采集/调度模式，Phase 09 才考虑事件接入和终端体验，Phase 10 才允许 Lean 执行结算原型；Fincept 默认保持只参考、不复制。
- 四个项目均不得成为研究、行情、组合、合理估值或真实成交的新真源；任何代码复用另行通过固定 revision、许可证、schema 和独立验收门。
