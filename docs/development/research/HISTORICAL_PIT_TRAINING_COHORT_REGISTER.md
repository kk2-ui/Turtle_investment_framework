# Turtle 历史训练对象与留出队列

状态：`TRAINING_ACTIVE / ENTERPRISE_JUDGMENT_V2_ADOPTED / FIRST_INDUSTRY_LEARNING_BLOCK_PLANNED / MINIMAL_EPISODE_PIPELINE_SETTLED / REPORT_USE_NOT_RELEASED`
更新：2026-08-26
上位协议：[历史训练体系重构](TURTLE_HISTORICAL_TRAINING_SYSTEM_REDESIGN.md)、[历史优先训练架构](TURTLE_HISTORICAL_FIRST_JUDGMENT_TRAINING_ARCHITECTURE.md)、[判断力验证与回测协议](TURTLE_JUDGMENT_VALIDATION_PROTOCOL.md)

## 1. 目的

这个 register 同时登记行业历史、evidence carriers、教学/生命周期案例、正式 Comparative Episodes 和留出。它不再把所有对象压成一个“必须先凑齐固定 cohort 才能训练”的队列。

机器真源仍是各 program config、不可变 receipts 和控制数据库；本文件解释对象身份、允许产物和下一门。分层 schema/validator 尚未实现，因此凡是新设计与当前 H1/H2/V5 运行时冲突，执行时仍以当前 validator 为准，禁止手工绕过。

## 2. 五个正交维度

| 维度 | 字段与可用值 | 约束 |
|---|---|---|
| 训练对象 | `object_class` | `INDUSTRY_UNIVERSE / EVIDENCE_CARRIER / TEACHING_CASE / LIFECYCLE_CASE / PIT_COMPANY_STATE_FORECAST / COMPARATIVE_EPISODE / LEARNING_EPISODE` |
| 主张强度 | `claim_class` | `DESCRIPTIVE_STRUCTURE / WITHIN_CASE_MECHANISM / LIFECYCLE_TRANSITION / FORECAST_CALIBRATION_COVERAGE / RELATIVE_CAUSAL / METHOD_GENERALIZATION / INVESTMENT_DECISION_UTILITY` |
| 运行通道 | `lane` | `HISTORICAL_TRAINING / HISTORICAL_HOLDOUT / HISTORICAL_TEACHING / LIVE_SENTINEL` |
| 来源与结果隔离 | `provenance_role + outcome_access` | `HISTORICAL_SELF_REPLAY + PIT_OUTCOME_SEALED`、`RESULT_KNOWN_TEACHING + OUTCOME_EXPOSED`、`REAL_FORWARD + NOT_YET_RELEASED` |
| 后续权限 | `learning_eligibility` | `BOUNDARY_METHOD_ELIGIBLE / FORECAST_POLICY_ONLY / SELECTION_METHOD_ELIGIBLE / EVALUATION_ONLY / TEACHING_ONLY / MECHANISM_SETTLEMENT_ONLY / CONTEXT_ONLY` |

Industry Universe 和 Evidence Carrier 不自动成为 episode。Teaching/Lifecycle 可训练问题、机制边界、near miss 和 permanent-loss pattern，但不得进入选择成绩。只有 `RELATIVE_CAUSAL + COMPARATIVE_EPISODE + PIT_OUTCOME_SEALED` 才可能产生方向性 learning；`MIXED / NOT_DIAGNOSTIC / MEASUREMENT_MISMATCH` 只形成边界。

## 3. 生命周期身份

历史 risk set 必须保留后来退出的公司，并区分：

```text
SURVIVED
ACQUIRED
MERGED_OR_PERIMETER_TRANSFERRED
DELISTED_BUT_OPERATING
BANKRUPTCY_FILED
REORGANIZING
EMERGED_FROM_REORGANIZATION
RESTRUCTURING_FAILED
LIQUIDATED
EXITED_BUSINESS
DATA_CENSORED
```

观察状态另记 `OBSERVED / CENSORED / COMPETING_EVENT_OBSERVED / UNKNOWN / NOT_DIAGNOSTIC / MEASUREMENT_MISMATCH`。退出公司不能因资料难找被删除，`CENSORED` 不能自动判输，并购、破产重组、清算或退市也不能统一解释为失败。`economic_entity / legal_entity / listed_security / reporting_perimeter / successor_entity` 分开并带有效期；经营结果、owner-cash recovery 和证券 terminal return 分开结算。后续资料只能作为 `POST_CUTOFF_CONTEXT` 或 `OUTCOME`，不得倒灌 cutoff 前判断。

## 4. 当前对象

| ID | 对象与工件 | object / claim | lane / permission | 当前价值 | 禁止事项与下一门 |
|---|---|---|---|---|---|
| `HTR-01` | [R-62 鹏鼎 2023 cutoff screen](experiments/R-62_pengding_automotive_pcb_2023_screen/01_pre_outcome_admission_screen.md) | `EVIDENCE_CARRIER / WITHIN_CASE_MECHANISM` | `HISTORICAL_TRAINING / CONTEXT_ONLY` | 当前为 `NO_PRIMARY / NOT_FROZEN`；可训练“不要以项目审批、认证或集团代理越过责任单元”的拒绝边界。 | 未形成 PIT case、结果合同或独立审阅；不得登记 control、读取 outcome 或生成 learning。 |
| `HTR-02` | R-69 联赢激光 backlog／扩产 screen | `EVIDENCE_CARRIER / WITHIN_CASE_MECHANISM` | `HISTORICAL_TRAINING / CONTEXT_ONLY` | 当前同样保持 `NO_PRIMARY / NOT_FROZEN`；订单和建设期不能替代订单—产能—现金的可结算链。 | 不得以未冻结 case 或后来结果声称 boundary application。 |
| `HTR-03` | [R-61 沪硅历史留出](experiments/R-61_shanghai_silicon_2025_minorities_screen/01_pre_outcome_admission_screen.md) | `COMPARATIVE_EPISODE / METHOD_GENERALIZATION` | `HISTORICAL_HOLDOUT / EVALUATION_ONLY` | 当前保持 PIT outcome sealed，等待有效选择方法冻结。 | 不得读取 outcome；R-62/R-69 筛查或边界教学不能释放它。 |
| `HTR-04` | [R-25 美的扩产教学](experiments/R-25_midea_2004_capacity_chain_teaching/01_2004_pre_outcome_capacity_card.md) | `TEACHING_CASE / WITHIN_CASE_MECHANISM` | `HISTORICAL_TEACHING / TEACHING_ONLY` | 训练产能吸收、单位经济、现金转换、资本回收分层。 | 不用于方法效果、选择准确率或管理层总评。 |
| `HTR-05` | [R-21 长虹 APEX](experiments/R-21_changhong_apex_credit_growth/01_2003_pre_outcome_enterprise_judgment_card.md) | `TEACHING_CASE / WITHIN_CASE_MECHANISM` | `HISTORICAL_TEACHING / TEACHING_ONLY` | 训练增长、客户信用、现金和继续扩张的非嵌套反方。 | 不用后来坏账倒推当时全部决策质量。 |
| `HTR-06` | [R-78 Ford Way Forward](experiments/R-78_ford_way_forward_2006/02_outcome_resolution.md) | `LIFECYCLE_CASE / LIFECYCLE_TRANSITION` | `HISTORICAL_TEACHING / TEACHING_ONLY` | 训练退出实施、客户、单位经济、现金和资本回收分离。 | 不把美国汽车参数迁为中国参数。 |
| `HTR-07` | 梅花生物价格竞争 | `EVIDENCE_CARRIER / UNCLASSIFIED` | `INTAKE / CONTEXT_ONLY` | 等待核实具体时期、产品、行动和原始来源。 | 不能据二手评论、后来利润或股价判断价格权。 |
| `HTR-08` | [R-104 重庆啤酒生产网络优化](experiments/R-104_chongqing_beer_network_pruning_unit_economics_20160430/11_independent_post_outcome_review.json) | `COMPARATIVE_EPISODE / WITHIN_CASE_MECHANISM` | `HISTORICAL_TRAINING / MECHANISM_SETTLEMENT_ONLY` | D3=`A_ONLY`、D4=`B_ONLY`、联合=`MIXED`；证明经营改善不自动传到正常 owner cash。 | 禁止方向性 learning、方法冻结、R-103 释放和报告授权。 |
| `HTR-09` | [水泥 2018 H1 static package](cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json) | `INDUSTRY_UNIVERSE + EVIDENCE_CARRIER / DESCRIPTIVE_STRUCTURE` | `HISTORICAL_TRAINING / E0-E1_RECONSTRUCTION` | strict preflight=`STAGE0_FEASIBILITY_REVIEWABLE`；25 份 PDF、五家公司和既有六 cutoff series 作为首个真实 `IndustryLearningBlock` seed；独立 curator 的 H2 `NO_PRIMARY_ACTION_SCOPE` 只关闭其 Comparative 候选。 | 不是 final peer panel；两家 scope/control break 仍保留为 lifecycle/archetype，不得进入不匹配 comparator；不得把 E0/E1 或地方性/例行事项升级为 company-wide causal intervention。 |
| `HTR-10` | [华新水泥 2017 perimeter-break teaching case](cohorts/TEACHING_LIFECYCLE_CN_600801_PERIMETER_BREAK_20170324.json) | `TEACHING_CASE / WITHIN_CASE_MECHANISM` | `HISTORICAL_TEACHING / TEACHING_ONLY` | 以 FY2016 年报 p9 的 15 家工厂收购批准训练“scope break 不等于经营退出”，并保留 action-window perimeter bridge 问题。 | 不得把收购批准当作已观察到的业务退出，或把该教学案例升级为 comparative/learning/report/investment 权限。 |
| `HTR-11` | CN:600585 2018 `Forecast V4` contract-first receipt | `PIT_COMPANY_STATE_FORECAST / FORECAST_CALIBRATION_COVERAGE` | `HISTORICAL_TRAINING / FORECAST_POLICY_ONLY` | 已完成独立 settlement；仅保留 coverage / direct forecast policy 和 `RESEARCH_AGENDA`。 | outcome access 前没有 method 或 decision-utility pairing；不得回填，亦不得声称方法改善、跨公司迁移、决策效用、method release、CJO、估值或报告权限。 |
| `HTR-12` | CN:600585 2018 `Minimal Historical Episode v1` | `PIT_COMPANY_STATE_FORECAST / FORECAST_CALIBRATION_COVERAGE` | `HISTORICAL_TRAINING / MECHANICAL_SETTLEMENT_ONLY` | 独立完成 `Decision Contract → Measurement Contract → static evidence → blind prediction → contract-only custodian access → mechanical settlement`；只证明单公司、单指标的无泄漏管线可闭合。 | 固定 `NO_METHOD_TRANSFER_RIGHTS`；不产生方法分数、learning、跨公司迁移、CJO、估值、报告或投资权限，也不替代 Comparative Episode。 |
| `HTR-13` | CN:600802 2018 `Minimal Historical Episode v1` | `PIT_COMPANY_STATE_FORECAST / FORECAST_CALIBRATION_COVERAGE` | `HISTORICAL_TRAINING / MECHANICAL_SETTLEMENT_ONLY` | 冻结到 contract-only outcome access；允许入口未能唯一定位 FY2018 官方静态 PDF 的逐页指标字段，故维持 `MEASUREMENT_MISMATCH`，未写 observation 或 settlement。 | 不以二手副本、搜索摘要或不确定来源补标签；先修复官方静态来源定位/映射能力，才可由同一 custodian 继续。固定 `NO_METHOD_TRANSFER_RIGHTS`，不产生学习、CJO、估值、报告或投资权限。 |
| `HTR-14` | CN:600425 FY2018 operating-revenue `Minimal Historical Episode v1` | `PIT_COMPANY_STATE_FORECAST / FORECAST_CALIBRATION_COVERAGE` | `HISTORICAL_TRAINING / MECHANICAL_SETTLEMENT_ONLY` | 已获授权的 contract-only custodian access 后，value-free source inventory 返回 `MEASUREMENT_MISMATCH / NO_UNIQUE_DIRECT_ANNUAL_REPORT`；没有 observation、settlement 或 outcome label。这是保护性的 `ACQUISITION_MODULE + DATA_COVERAGE` 终态，不是企业经营表现的负面结论，也不是已结算训练样本。 | 不得以任意来源替换、二手副本、搜索摘要或不确定映射补标签；固定 `NO_METHOD_TRANSFER_RIGHTS`，不产生方法分数、learning、跨公司迁移、CJO、估值、报告或投资权限。 |
| `HTR-15` | CN:002003 FY2020 operating-revenue `Minimal Historical Episode v1` | `PIT_COMPANY_STATE_FORECAST / FORECAST_CALIBRATION_COVERAGE` | `HISTORICAL_TRAINING / MECHANICAL_SETTLEMENT_ONLY` | 已有授权的 contract-only access 和 value-free source inventory；inventory 返回 `MEASUREMENT_MISMATCH / CNINFO_ORGANIZATION_ROUTE_UNAVAILABLE`，因此 observation、settlement、outcome value 与 label 均为零。这是保护性的 `ACQUISITION_MODULE` 终态，不是企业经营表现的负面结论，也不是已结算训练样本。 | 不得以人工 route、任意来源、二手副本、搜索摘要或不确定映射补标签；固定 `NO_METHOD_TRANSFER_RIGHTS`，不产生方法分数、learning、跨公司迁移、CJO、估值、报告或投资权限。该 v1 只保留 history/readability；后续新对象必须在 prediction 前采用 Outcome Route Contract v2 和 controller-owned `TECHNICAL_ROUTE_IDENTITY`。 |
| `HTR-16` | CN:002404 FY2020 operating-revenue `Minimal Historical Episode v2` | `PIT_COMPANY_STATE_FORECAST / FORECAST_CALIBRATION_COVERAGE` | `HISTORICAL_TRAINING / MECHANICAL_SETTLEMENT_ONLY` | v2 在 prediction 前已由 controller 冻结 Outcome Route Contract 与 `TECHNICAL_ROUTE_IDENTITY`；随后授权的 contract-only custody 记录 access=1、value-free inventory=1，inventory 返回 `MEASUREMENT_MISMATCH / NO_UNIQUE_DIRECT_ANNUAL_REPORT`。observation、settlement、outcome value 与 label 均为零。这是保护性的 `ACQUISITION_MODULE` 终态，不是企业经营表现的负面结论，也不是已结算训练样本。 | 不得替换来源、retrofit 既有对象，或以二手副本、搜索摘要和不确定映射补标签；固定 `NO_METHOD_TRANSFER_RIGHTS`，不产生方法分数、learning、跨公司迁移、CJO、估值、报告、投资或 method-transfer 权限。 |

R-61 是当前预留的 PIT outcome-sealed holdout；R-102 的联合结果与基线均 `NOT_DIAGNOSTIC`，只保留 `MEASUREMENT_BOUNDARY`。R-56、R-58 及其他结果已知案例只能映射为 Teaching/Lifecycle，不得重新包装成 formal learning。

## 5. 水泥 cohort 裁决

[旧 feasibility prototype](cohorts/COHORT_CN_CEMENT_LISTED_20180430_feasibility.json) 的 `STAGE0_REJECTED` 只说明旧包缺 curator attestation、static identity 和机制 arena，不能覆盖新 H1 receipt。新 H1 已通过 source intake，但这也不等于其 final comparator 容量闭合。

新设计下五家公司都留在 2018 Industry History Universe；三家 `PENDING_ACTION_WINDOW_REVIEW` 可进入 H2 action screen，两家 `KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK` 可继续承载行业史或 Teaching/Lifecycle。若 H2 找到已实施行动，未来实现应允许 curator 在结果读取前按冻结 eligibility predicate 追加 static peer-recruitment batch；最终仍不足则降级为 Teaching/Lifecycle，而非废弃整批资料。

在 Enterprise Judgment V2 下，该 H1 另承担首个真实 `IndustryLearningBlock` 的 E0/E1 输入。所有五家公司进入 cutoff risk set；E1 深挖按结果前的材料性、公司状态差异和字段覆盖选择，scope/control break 本身是 archetype/lifecycle 信息，不再被当作整批无效。E0/E1 只形成行业时期、公司状态、决策账本、关键未知和条件化研究问题；它不依赖 H2，也不能据此生成因果、方法、CJO、估值或投资权限。

该追加能力尚未实现。当前 runtime 仍要求 H2 绑定原 H1 receipt 且不得新增公司，因此实现迁移前只能运行旧合同允许的 H2，不能手工补同行。

## 6. 并行运行顺序

### A. Universe / Lifecycle

1. 以 cutoff 和机制定义 risk set；
2. 记录覆盖边界、进入退出、实体/证券/业务连续性；
3. 对 outcome 写 `OBSERVED/CENSORED/UNKNOWN`；
4. 只向 `RESEARCH_AGENDA` 输出 cutoff-safe 行业结构和生命周期问题。

### B. Teaching / Boundary

1. 对一个公司或一个行动冻结企业状态、机制、最强反方和 process evidence；
2. 允许已知结果，但过程判断与结果评价分开；
3. 形成 near miss、禁止替代、测量边界和 acquisition 改进；
4. 不生成 selection learning、method freeze 或 report-use。

### C. Comparative / Learning

1. 登记 `RELATIVE_CAUSAL`、intervention、time zero 和 comparator eligibility；
2. 只读 cutoff-before static receipts，闭合 target/peer D3/D4 和 cash bridge；
3. Comparative Panel Freeze 后关闭 roster、顺序、来源和结果合同；
4. 独立 custodian 结算；只有方向性诊断可申请 learning；
5. learning 必须改变不同公司的冻结前字段并独立复核；
6. method freeze 后才由隔离 evaluator 处理 R-103。

## 7. 当前成功定义

短期成功不是“凑出五家公司”，而是完成三类互不冒充的闭环：

```text
IndustryLearningBlock
  -> Industry Epoch + company archetypes + longitudinal E0/E1 episodes
  -> conditional mechanism synthesis + research agenda

Minimal Historical Episode -> blind observation -> mechanical settlement
  -> 管线完整性证据（无方法迁移权）

Comparative Episode -> diagnostic settlement
  -> cross-company application -> method freeze
  -> R-103 holdout -> Golden Report use decision
```

第一条链现在是主线，并从水泥真实 block 开始；最小链已验证一项真实单公司结算的管线纪律；第三条链仍缺真实方向性 episode，但只是一条并行高级支线。三者都不能单独证明实时预测优势、投资收益或一般性的企业判断能力。
