# R-10 第二遍：ZTO Q1 2023 解释攻击

状态：`PRE_OUTCOME_SECOND_PASS_COMPLETE / NO_PRIMARY / OUTCOME_UNREAD`

本记录只在 [R-10 冻结卡](00_zto_q1_2023_pre_outcome.md) 完成后读取同一份 Q1 原件的解释、预期和此前未纳入第一遍的单位指标；尚未打开 Q2 结果文件。

## 1｜新增的量化信息与公司叙事，必须分开处理

| Q1 原件信息 | 类别 | 对冻结机制的处理 | 限制 |
|---|---|---|---|
| 核心快递单件价格同比下降 3.7%。 | `FACT / H-B pressure point` | 比第一遍的“总收入/件”更接近价格变量，确认量增并不代表每件收入改善。 | 仅凭下降幅度无法判断网络效率是否足以持续抵消。 |
| 单位运输成本下降 10.6%，单位分拨枢纽成本下降 11.1%。 | `FACT / H-A efficiency point` | 这是与价格变量独立的成本端观察，支持 H-A 的当期网络效率箭头。 | 它是当期事实，尚不能证明 Q2 仍成立。 |
| 公司将结果描述为精细定价、数字化和成本生产率的成果。 | `CAUSAL_ATTRIBUTION / H-A compatible` | 作为待检验的 H-A 叙事。 | 不是独立于公司自述的因果证据。 |
| 管理层上调全年件量目标至同比增长 20%–24%。 | `FORECAST / common background` | 记录为对件量的公司预期。 | 不对 Q2 毛利率或枢纽成本率给出可结算预期，不能替代冻结观察。 |
| 竞争风险的泛化表述。 | `RISK / NOT_DIAGNOSTIC` | 不用于 H-B 选择。 | 没有承诺同口径价格、成本或毛利的未来路径。 |

所有内容均来自 [ZTO Q1 2023 Form 6-K exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1677250/000110465923062034/tm2315927d1_ex99-1.htm) 的经营结果、成本说明和 outlook 段。

## 2｜对 R-10 的含义

两组数值同时存在：单件价格下降支持 H-B 的压力点，单位运输/分拨成本更快下降支持 H-A 的效率点。公司对原因的解释不能使任一方成为主路径，所以 `NO_PRIMARY` 维持，冻结的 Q2 双观察也不改写。

本例还触发 [P-60.2](../../TURTLE_RESEARCH_PREPARATION_ITERATION_LOG.md) 的流程修复：这些有用数值与归因相邻，第一遍的“整段排除”会错误丢掉变量，进而以总收入/件作宽口径代理。今后由 `FROZEN_METRIC_SLICE` 先隔离指标数值，再在第二遍读归因；本卡因研究者已见到完整原件，继续是 `CONTEXT_SEPARATION_NOT_ASSURED` 的教学材料。

## 3｜结果读取授权

第一遍阈值、第二遍攻击和这个限制均已记录。现在只可打开已登记 Q2 exhibit，并且只提取 `revenues`、`gross profit`、`sorting hub operating cost` 的同口径表行；不得使用 Q2 管理层说明、Q3 展望、价格、回报或以后资料。
