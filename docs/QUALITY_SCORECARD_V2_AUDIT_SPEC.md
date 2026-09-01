# V13 质量评分卡 V2：审计规格

> 状态：**待人工审计，不得视为最终投资研究质量标准**  
> 实现真源：`scripts/absolute_quality_scorecard.py`  
> 相关真源：`scripts/chapter_depth.py`、`scripts/research_plan.py`、`scripts/evidence_citation.py`、`scripts/report_completion.py`  
> 目的：完整披露当前规则、算法、边界和已知缺陷，供决定是否允许评分卡驱动自动修复。

## 1. 这套评分卡是什么，不是什么

评分卡由两部分组成：

1. **硬契约**：只检查机器可复现的文件、来源身份和真实研究执行记录；失败会进入 completion contract，阻断发布。
2. **软质量雷达**：用确定性文本信号估计研究问题覆盖、因果推理、证据连接、反证、可证伪性、推导和叙事效率；只产生 A/B/C/D 和 WARN。

当前软分不是：

- 人工投资报告百分制；
- 公司投资价值评分；
- 事实正确率；
- 模型洞察力的完整衡量；
- 允许用 76 与 75 宣称精确优劣的统计量。

在完成本文审计和多样本人工校准前，软分只适合：

- 定位明显薄弱章节；
- 给人工复核排序；
- 观察同一规则版本下的大幅退化。

它目前**不应直接成为新的发布硬门**，也不应在无人复核的情况下驱动无限自动重写。

## 2. 三层质量体系及发布关系

| 层级 | 实现 | 作用 | 当前是否阻断发布 |
|---|---|---|---:|
| 完成契约 | `report_completion.py` | 文件、标题、语义深度、审计账本、GG 推导、决策身份 | 是 |
| 评分卡硬契约 | `absolute_quality_scorecard.py` | 未知来源、真实读取记录、跨年与规定工具执行 | 是 |
| 评分卡软雷达 | `absolute_quality_scorecard.py` | 研究与写作质量的启发式信号 | 否，只 WARN |
| 历史参考防退化 | `legacy_reference_regression.py` | 防止旧稿已有内容大面积丢失 | 当前 FAIL 会阻断 |

注意：历史参考层仍可能阻断发布，但它不属于本评分卡的绝对质量分。旧稿不是金标准，这条阻断规则也应单独审计。

## 3. 输入、范围与报告聚合

### 3.1 输入

评分器读取：

- `chapters/_ch00.md` 至 `_ch14.md`；若不存在则回退读取输出目录根部的同名文件；
- 输出目录下实际存在的 JSON、PDF、`20XX_年报.md`，用于注册来源身份；
- `research_execution.json`，用于核对本次运行真实工具调用；
- `CHAPTER_RESEARCH_SPECS`，用于逐章问题、年报章节和工具要求；
- `chapter_depth.py` 的文本指标和章节深度目标。

### 3.2 数据丰富档

满足以下两项时，标的被判为 `data_rich=True`：

- `mda.json / segments.json / risks.json / governance.json / audit.json` 中至少四类有效；
- 输出目录至少有四份 `20XX_年报.md`。

数据丰富档会提高深度要求，并影响软雷达的因果和推导分母。

### 3.3 报告聚合

- 15 章等权平均，未按关键章或篇幅加权。
- 任一章出现评分卡硬失败：报告 `status=FAIL`。
- 无硬失败但任一章有软预警：报告 `status=WARN`。
- 全章无硬失败且无预警：报告 `status=PASS`。
- `hard_contract_status` 只看评分卡硬失败，不看软预警。

## 4. 评分卡硬契约：当前精确规则

### 4.1 硬失败表

| 规则代码 | 触发条件 | 适用范围 | 说明 |
|---|---|---|---|
| `missing_file` | `_chXX.md` 不存在 | 全部章节 | 与 completion contract 重叠 |
| `unknown_source_components:N` | `[source: ...]` 无法映射到任何已注册或伪来源身份 | 全部章节 | 一个未知组件即硬失败 |
| `research_execution_missing` | 台账根节点 `enforced=true`，章节在 `expected_chapters`，但没有章节记录 | 本次要求生成/修复的章节 | 防止沿用旧正文直接 assemble |
| `required_source_reads_missing:A,B` | 章节台账的 `missing_sections` 非空 | `entry.enforced=true` 的章节 | 检查规定年报章节是否实际读过 |
| `required_fiscal_year_reads_missing:N/2` | 章节写入时记录的不同财年少于两个 | `entry.enforced=true` 的章节 | `read_section` 或 `search_report` 的年份均可进入财年集合 |
| `required_search_report_missing:N/3` | 研究计划要求 `search_report`，有效调用少于三次 | 当前为 Ch4、Ch9 | 只有返回有效 hit 的调用才入账 |
| `required_web_search_missing:N/2` | 研究计划要求 Web，搜索有效结果少于两次 | 当前为 Ch2、Ch8 | 空结果不入账 |
| `required_web_fetch_missing:N/1` | 研究计划要求 Web，但未成功读取至少一篇正文 | 当前为 Ch2、Ch8 | 验证码/WAF/空正文不入账 |

### 4.2 台账可信边界

自动 unified 管线默认开启 `source_deepening`。台账包含：

- `run_id`；
- 本次预期章节；
- 每章写入时已经发生的工具调用；
- 实际读取的 section、财年、搜索词、URL 与工具计数。

新 pipeline 初始化时会清空不同 `run_id` 的旧台账。正文中写“已读取 NOTES”不会生成台账记录。

当前仍有两个边界：

1. 评分器本身不读取 pipeline diagnostics 来二次比对 `run_id`，而是信任已初始化的台账文件；离线手工伪造 JSON 仍可绕过。
2. 年份规则要求“合计覆盖两个财年”，没有要求每一个 required section 都分别覆盖两个财年。

### 4.3 来源身份解析规则

可解析身份包括：

- 输出目录中真实存在的 JSON、PDF、`20XX_年报.md`；
- 工具别名，例如 `compute_gg → compute_bundle.json`、`get_financial_trends → financial_trends.json`；
- 年报文字形式，例如“2025年报”；
- 报告内部章节引用 `Ch0–Ch14 → report_internal`；
- 框架、报告内推导、数据库和公开市场研究等伪来源身份；
- 域名或明确的 `web_search/web_fetch` 描述 → `public_market_research`。

重要缺陷：复合锚点只要识别出一个合法来源，当前解析器会清空该锚点其余未识别部分。因此：

```text
[source: compute_bundle.json + invented_database]
```

可能不会报告 `invented_database`。这是硬契约的真实逃逸口，审计通过前应列为高优先级修复项。

## 5. 软质量雷达：公式、权重与阈值

### 5.1 总分公式

每章内部启发式分：

```text
S = 15% × 研究问题
  + 20% × 因果推理
  + 20% × 断言邻证
  + 10% × 来源质量
  + 10% × 反证
  + 10% × 可证伪
  + 10% × 推导
  +  5% × 效率
```

每个维度先归一到 `[0,1]`，再乘权重。章节分保留一位小数，报告平均分四舍五入为整数。

### 5.2 维度一：研究问题回答，15%

逐章读取研究计划中的 topic。一个 topic 被认为已回答，必须满足：

1. 段落包含该 topic 至少一个关键词；并且
2. 同一段落至少满足以下一个“实质性”条件：
   - 同时包含来源锚点与任意数字；
   - 同时包含因果词与财务/决策影响词；
   - 段落不少于 60 字符，且包含带单位数字。

公式：

```text
research_questions = 已回答 topic 数 / 本章 topic 总数
```

预警：`research_questions < 75%`。

已知问题：

- 判断的是关键词共现，不是真正回答了问题；
- 一个长段落可同时满足多个 topic；
- 同义表达不含关键词时会漏判；
- 加入看似合理的数字和因果词仍可能游戏化。

### 5.3 维度二：因果推理，20%

先按中文句号、问号、感叹号、分号和换行切成语义单元。

一个“因果链单元”必须在同一单元内同时包含：

- 因果词；
- 财务/估值/决策影响词；
- 任意数字或来源锚点。

目标数：

- Ch0–Ch9：4 个；
- Ch10–Ch14：6 个。

同时复用 `chapter_depth` 的分析单元数量：

```text
analysis_ratio = min(1, 分析单元数 / 本章分析目标)
causal_ratio   = min(1, 因果链单元数 / 4或6)
causal_reasoning = (analysis_ratio + causal_ratio) / 2
```

预警：`causal_reasoning < 60%`。

已知问题：

- 只检查词语共现，不验证因果方向和逻辑是否成立；
- 跨句因果链容易漏判；
- “因为……所以……”模板可被重复堆砌；
- 普通数字也可满足第三项，不要求数字与因果事实相关。

### 5.4 维度三：数字断言—证据相邻性，20%

“数字断言行”是包含带单位数字的非标题行，单位包括 `% / pp / 倍 / x / 元 / 亿 / 万 / HKD / RMB`。

满足以下任一条件即视为有邻近证据：

- 来源锚点与数字在同一行；
- 来源锚点在该行上一行或下一行。

公式：

```text
claim_evidence = 有邻近来源的数字断言行 / 全部数字断言行
```

预警：`claim_evidence < 50%`。

重要边界：

- 如果一章完全没有带单位数字，当前维度返回 `100%`；
- Markdown 表格顶部或底部的共享来源通常只能覆盖相邻一两行，可能低估整张表；
- 相邻不等于来源真的支持该数字；
- 同一行放一个来源可让多个数字同时通过；
- 无单位数字、日期和部分公式不会进入分母。

### 5.5 维度四：来源质量，10%

对每一个 `[source: ...]` 做 canonical 化。若锚点至少映射到以下任一身份，则该锚点计为高质量来源：

- `compute_bundle.json`；
- `financial_statement_db`；
- `financial_trends.json`；
- `industry_context.json`；
- `mda.json / segments.json / risks.json / governance.json / audit.json`；
- `moat_assessment.json`；
- `public_market_research`；
- 输出目录中注册的 `20XX_年报.md`。

公式：

```text
source_quality = 映射到上述身份的锚点数 / 全部来源锚点数
```

预警：`source_quality < 60%`。没有任何来源锚点时为 `0%`。

以下身份可解析、不会触发未知来源硬失败，但不进入高质量来源分子：

- `report_internal`；
- `framework_method`；
- `report_derivation`。

已知问题：

- `public_market_research` 尚未按官方、主流媒体、咨询机构、自媒体分级；
- 域名能解析不代表内容可靠，也不验证发布日期和事实支持关系；
- 综合决策章合理引用前文章节时会被来源质量维度扣分；
- 每个锚点等权，年报原文与普通网页没有质量级差。

### 5.6 维度五：反证，10%

一个反证单元必须同时包含：

- 反证/转折词；
- 财务、估值、风险或决策影响词；
- 任意数字或来源锚点。

目标数：

- 关键章 Ch0、Ch9、Ch12、Ch13、Ch14：3 个；
- 其他章：2 个。

```text
counter_evidence = min(1, 反证单元数 / 目标数)
```

预警：`counter_evidence < 50%`。

已知问题：一个普通“但”字即可命中反证词；不判断反证是否真能挑战主论点，也不要求给出区分主解释与替代解释的验证方法。

### 5.7 维度六：可证伪性，10%

一个可证伪单元必须同时包含：

- 条件词；
- 动作词；
- 任意数字。

目标数：

- Ch9、Ch14：4 个；
- 其他章：2 个。

```text
falsifiability = min(1, 可证伪单元数 / 目标数)
```

只有 Ch0、Ch4、Ch7、Ch9、Ch13、Ch14 在低于 50% 时产生维度预警；其他章仍计分，但不会单独预警。

已知问题：

- 不要求数字带单位；
- 不要求阈值来自证据或合理基准；
- “如果2025年复核”也可能被错误计入；
- 不判断动作是否足够明确、可执行。

### 5.8 维度七：公式、情景与推导，10%

复用 `chapter_depth` 对推导单元的计数。命中符号或词语即可计数，例如：

```text
= ＝ ≈ → − + 公式 推导 拆解 调整后 归一化
基准 悲观 乐观 敏感 情景 假设 口径 折现 安全边际
相比 相较 因此 所以
```

```text
derivation = min(1, 推导单元数 / 推导目标)
```

数据丰富标的使用 source-deepening 的逐章高目标；标准数据档使用普通目标。

重要问题：普通定性章的 completion 深度目标允许 `min_derivation_lines=0`，但评分卡用 `max(1, target)`，因此完全没有推导词的定性章仍会在本维度丢失全部 10 分。这是否合理需要人工裁决。

### 5.9 维度八：叙事效率，5%

只统计不少于 40 字符的段落。去掉来源锚点、空白和部分 Markdown 符号后，计算**完全相同段落**比例。

空泛短语包括：

```text
众所周知 / 显而易见 / 不难发现 / 毋庸置疑 / 值得注意的是 / 总的来说
```

公式：

```text
efficiency = max(0, 1 - 2 × 完全重复段落比例 - 空泛短语次数 / 10)
```

已知问题：

- 只能发现完全重复，无法识别改写后的语义重复；
- 合法重复的风险提示也会被扣分；
- 未评价段落组织、句长、可读性和信息密度。

## 6. 软预警、等级与状态

### 6.1 章节预警

| 预警 | 条件 |
|---|---:|
| `soft_score<72` | 总分 `<72` |
| `research_questions<75%` | 研究问题 `<0.75` |
| `claim_evidence<50%` | 断言邻证 `<0.50` |
| `source_quality<60%` | 来源质量 `<0.60` |
| `counter_evidence<50%` | 反证 `<0.50` |
| `falsifiability<50%` | 仅指定六章且可证伪 `<0.50` |
| `causal_reasoning<60%` | 因果推理 `<0.60` |

推导和效率目前没有独立预警，只通过总分影响等级。

### 6.2 等级

| 等级 | 当前算法 |
|---|---|
| A | 分数 `≥85` 且没有任何预警 |
| B | 不满足 A，但分数 `≥72` |
| C | `60≤分数<72` |
| D | 分数 `<60` |

因此，95 分但存在一个维度预警会降为 B，而不是 A。

### 6.3 章节与报告状态

```text
章节 FAIL = 有硬失败
章节 WARN = 无硬失败，但有软预警
章节 PASS = 两者都没有

报告 FAIL = 任一章节 FAIL
报告 WARN = 无 FAIL，但至少一章 WARN
报告 PASS = 全部章节 PASS
```

报告等级用 15 章平均分套用同样 A/B/C/D 边界。A 还要求整份报告没有 WARN。

## 7. 逐章研究计划

下面列出会影响问题覆盖和硬执行记录的当前计划。括号内是 topic 身份，不是完整关键词表。

| 章 | 必读原文章节 | 计划工具 | 研究问题身份 |
|---:|---|---|---|
| Ch0 | MDA, STMT, NOTES | compute_gg, compute_ddm | thesis, conflict, trigger, downside |
| Ch1 | MDA, SEG | read_zone_data | revenue_engine, economics, concentration |
| Ch2 | MDA, SEG | web_search, web_fetch, get_peer_comparison | structure, position, competition, externality |
| Ch3 | MDA, SEG | read_zone_data | moat, evidence, erosion, counter |
| Ch4 | MDA, RISK | search_report | change, phase, signal |
| Ch5 | MDA, STMT, SEG | get_financial_trends | trend, margin, cash, segment |
| Ch6 | STMT, NOTES | compute_aa, get_financial_trends | balance, capex, allocation, quality |
| Ch7 | STMT, NOTES, GOV | compute_ddm | dividend, buyback, sustainability |
| Ch8 | GOV, NOTES | read_zone_data, web_search, web_fetch | control, incentive, related, counter |
| Ch9 | RISK, NOTES | search_report | risk_chain, veto, monitor, counter |
| Ch10 | STMT, NOTES | get_financial_trends, compute_gg | growth, scenario, bridge |
| Ch11 | STMT, NOTES | compute_aa, compute_gg | identity, formula, stress, distortion |
| Ch12 | STMT, NOTES | compute_gg, compute_ddm | methods, conflict, sensitivity, margin |
| Ch13 | STMT, NOTES | compute_ddm, get_market_data | ddm, return, position, downside |
| Ch14 | MDA, RISK, STMT, NOTES | compute_gg, compute_ddm | synthesis, conflict, execution, monitor |

硬台账目前只专门计数 `read_section / search_report / web_search / web_fetch`。表中的计算工具和 Zone 工具由其他合同与审计约束，但不在评分卡硬台账中逐项强制。

### 7.1 当前完整 topic 关键词表

每个 topic 只需命中下列关键词中的任意一个，再满足第 5.2 节的“实质性”条件，即被计为回答。

| 章 | topic 与关键词 |
|---:|---|
| Ch0 | thesis: 投资逻辑 / 核心判断 / 一眼看懂<br>conflict: 定性 / 定量 / 冲突 / 裁决<br>trigger: 触发 / 买入价 / P* / 监控<br>downside: 风险 / 否决 / 下行 |
| Ch1 | revenue_engine: 收入 / 产品 / 客户 / 地区<br>economics: 毛利率 / 价值链 / 供应商 / 渠道<br>concentration: 集中 / 主业 / 多元化 / 分部 |
| Ch2 | structure: 行业 / 增速 / 周期 / 渗透率<br>position: 市占率 / 份额 / 排名 / 价格<br>competition: 竞争 / 对手 / 小米 / 美的<br>externality: 政策 / 原材料 / 技术 / 传导 |
| Ch3 | moat: 护城河 / 品牌 / 规模 / 网络<br>evidence: 溢价 / 毛利率 / ROIC / 超额<br>erosion: 侵蚀 / 衰减 / 约束 / 领先指标<br>counter: 反证 / 替代 / 失效 |
| Ch4 | change: 同比 / 变化 / 下降 / 增长<br>phase: 周期 / 结构 / 扰动 / 阶段<br>signal: 季度 / 拐点 / 信号 / 合同负债 |
| Ch5 | trend: 营收 / 净利润 / 趋势 / 驱动<br>margin: 毛利率 / 费用率 / 价格 / 成本<br>cash: OCF / 现金流 / OCF/NP / 含金量<br>segment: 分部 / 内销 / 外销 / 主业 |
| Ch6 | balance: 现金 / 债务 / 营运资本 / 合同负债<br>capex: 资本开支 / Capex / 折旧 / 维持性<br>allocation: 资本配置 / 分红 / 回购 / 投资<br>quality: 归一化 / 减值 / 一次性 / 应付账款 |
| Ch7 | dividend: DPS / 分红 / 派息 / 承诺<br>buyback: 回购 / 注销 / 股本 / 增厚<br>sustainability: 持续 / 覆盖 / 压力 / 自由现金流 |
| Ch8 | control: 控制权 / 董事会 / 关键人 / 接班<br>incentive: 激励 / 员工持股 / 股份支付 / 薪酬<br>related: 关联交易 / 担保 / 格力钛 / 减值<br>counter: 改善 / 反证 / 审计 / 承诺 |
| Ch9 | risk_chain: 传导 / 利润 / 现金 / 估值<br>veto: 否决 / 红线 / 触发<br>monitor: 领先指标 / 监控 / 阈值<br>counter: 缓冲 / 对冲 / 反证 |
| Ch10 | growth: 增长 / CAGR / 可持续 / 归一化<br>scenario: 悲观 / 基准 / 乐观 / 情景<br>bridge: 参数 / 映射 / g / II |
| Ch11 | identity: AA / FCFE / Normalized / 口径<br>formula: 公式 / 推导 / M / HH<br>stress: 敏感 / 压力 / 情景<br>distortion: AP / 少数股东 / 治理折价 / λ |
| Ch12 | methods: AV / EPV / DDM / P_base<br>conflict: 分歧 / 冲突 / 裁决 / 权重<br>sensitivity: 敏感 / 折现 / 增长 / 衰减<br>margin: 安全边际 / V_final / 回报安全边际 |
| Ch13 | ddm: DPS / DDM / 折现 / 终值<br>return: P* / 目标回报 / 买入价 / 反推<br>position: 仓位 / 阶梯 / 安全边际<br>downside: 削减 / 下行 / 压力 / 回撤 |
| Ch14 | synthesis: 定性 / 定量 / 合成 / 决策<br>conflict: 冲突 / 裁决 / 否决 / 拒绝<br>execution: 动作 / 仓位 / 触发 / 买入<br>monitor: 监控 / 跟踪 / 复核 / 阈值 |

这里存在明确的样本污染：Ch2 的“小米/美的”和 Ch8 的“格力钛”来自格力语境，却被写入所有公司的通用规则。虽然每个 topic 还有其他通用关键词，因此不一定直接造成失败，但它证明当前 topic 词表尚未完成行业中立化。在评分卡驱动自动修复前，应移除公司专名或改成由同行/重大投资数据动态生成。

## 8. 与语义深度门的关系

评分卡不是唯一质量规则。completion contract 还会调用 `chapter_depth.py`：

| 档位 | 定性章 Ch0–Ch9 | 定量章 Ch10–Ch14 |
|---|---|---|
| 标准数据 | 2200 实质字符、6 数字单元、6 分析单元、6 基础来源、3 小节 | 3000 实质字符、15 数字、8 分析、8 推导、10 基础来源、3 小节 |
| 数据丰富 | 3500 实质字符、12 数字、15 分析、6 基础来源、4 小节 | 5000 实质字符、25 数字、20 分析、20 推导、10 基础来源、4 小节 |

部分关键章有更高来源基础值：Ch0=8，Ch4/8/9=12，Ch11/12=18，Ch13=20，Ch14=15。

最终来源要求还会动态取：

```text
max(章节基础来源数, ceil(含单位数字声明行 × 25%))
```

开启数据丰富来源深化时，逐章额外目标如下：

| 章 | 实质字符 | 分析单元 | 推导单元 | 特殊来源要求 |
|---:|---:|---:|---:|---:|
| 0 | 5000 | 35 | 45 | — |
| 1 | 4500 | 30 | 15 | — |
| 2 | 4200 | 28 | 15 | — |
| 3 | 4500 | 32 | 18 | — |
| 4 | 3500 | 25 | 15 | — |
| 5 | 3800 | 30 | 25 | — |
| 6 | 4500 | 35 | 25 | — |
| 7 | 3600 | 24 | 20 | — |
| 8 | 4800 | 35 | 25 | 20 |
| 9 | 4800 | 42 | 25 | — |
| 10 | 5800 | 40 | 70 | — |
| 11 | 6200 | 35 | 80 | — |
| 12 | 6200 | 28 | 100 | — |
| 13 | 6200 | 35 | 100 | — |
| 14 | 6500 | 50 | 90 | — |

这些阈值来自少量已观察报告，不是统计学标定结果，也存在行业偏差和“为达数量而写作”的风险。

## 9. 已有对抗测试覆盖

当前测试验证了：

- 完全没有历史参考也能计算评分；
- 极薄章节只产生软降级，不冒充硬失败；
- 未知来源产生硬失败；
- 缺失规定年报章节产生硬失败；
- 本次 run 缺少章节执行记录产生硬失败；
- 完整执行记录可以通过；
- Web 计划只有搜索、没有读取正文时产生硬失败；
- 单纯堆砌 topic 关键词不会通过研究问题覆盖；
- 评分卡硬失败会进入 completion contract。

当前没有充分测试：

- 合法来源后拼接虚假来源；
- 表格共享来源；
- 跨句因果与跨段反证；
- 语义重复；
- 虚假但格式合规的数字阈值；
- 网页权威等级与发布日期；
- 多行业人工盲评一致性。

## 10. 当前样本校准结果

| 样本 | 当前等级 | 内部分 | 硬契约 | 解读限制 |
|---|---:|---:|---|---|
| 格力电器 Stage 7 冷启动 | B | 76 | PASS | 用户相对认可，但不是金标准；旧产物无本次研究台账，状态 UNKNOWN |
| 金融街物业当前稿 | C | 62 | PASS | 多个章节推导和邻近引用偏弱；旧产物无本次研究台账，状态 UNKNOWN |
| 对抗性关键词堆砌样本 | D | 测试内断言 | PASS | 证明关键词列表本身不能通过软雷达，不证明所有游戏化均已封堵 |

两只真实公司不足以证明权重合理，也不足以确定 72/85 是正确边界。

## 11. 审计中建议重点裁决的问题

请对下列问题逐项给出“保留 / 修改 / 删除 / 需样本验证”：

1. 软分是否继续采用 15 章等权，还是提高 Ch0/9/12/13/14 权重？
2. 因果与邻近证据各占 20% 是否过高？
3. 来源质量是否应从二元有效改成来源等级和主张支持关系？
4. 没有数字断言时，邻证应为 100%、0%、N/A，还是按章类型处理？
5. 定性章是否应有统一 10% 推导维度，还是改成机制分析/竞争性解释？
6. Ch9/Ch14 四个可证伪触发器是否会诱导制造阈值？
7. 反证数量目标是否应改成“至少一条完整竞争性解释”，而不是数两三个转折句？
8. A 必须无任何预警是否过严？B/C/D 的 72/60 边界依据是否充分？
9. `public_market_research` 是否必须拆成官方、公司披露、权威统计、主流媒体、其他五档？
10. 历史参考 FAIL 是否仍应阻断，还是只能 WARN？
11. 软雷达是否只用于推荐修复，不得自动改写已经人工确认的章节？
12. 数据丰富档按“4类 Zone + 4份年报”判定是否过于粗糙？

## 12. 建议的启用门槛（尚未实施）

在让评分卡驱动正式自动修复前，建议至少完成：

1. 修复复合来源逃逸口；
2. 将无数字断言的邻证从自动满分改成 N/A 或章型规则；
3. 对表格共享来源建立显式语法或表级证据映射；
4. 将来源质量拆分为“身份质量”和“是否支持主张”；
5. 准备至少 6 份跨行业报告，由人工盲评 A/B/C/D，再观察规则排序一致性；
6. 加入强文弱格式、弱文强格式、关键词堆砌、来源堆砌、虚假阈值五类对抗样本；
7. 只有人工排序与机器排序基本一致后，才允许软雷达自动选择修复章节；
8. 即便启用，也应限制修复次数，并冻结已验证的数值、来源和决策身份。

这部分是审计建议，不是当前代码行为。

## 13. 复现实验

运行评分卡：

```bash
.venv/bin/python scripts/absolute_quality_scorecard.py \
  --output-dir output/000651_格力电器_stage7_coldstart
```

查看机器结果：

```text
output/<标的>/absolute_quality_scorecard.json
```

查看人读摘要：

```text
output/<标的>/absolute_quality_scorecard.md
```

运行当前相关回归：

```bash
.venv/bin/python -m pytest -q \
  tests/test_stage10_absolute_quality.py \
  tests/test_auto_repair_pipeline.py \
  tests/test_completion_contract_v13.py
```

## 14. 正则与词表附录

### 因果词

```text
因此 / 所以 / 意味着 / 导致 / 驱动 / 传导 / 反映 / 取决于 / 从而 / 这使得 / 原因
```

### 影响词

```text
收入 / 利润 / 毛利 / 现金流 / 资本开支 / 估值 / 折现 / 回报 / 仓位 / 买入 / 决策 / 风险
```

### 反证词

```text
反证 / 但 / 然而 / 相反 / 替代解释 / 不成立 / 失效 / 未必 / 另一方面 / 对冲
```

### 条件词

```text
若 / 如果 / 当…时 / 一旦 / 除非
```

### 动作词

```text
上调 / 下调 / 否决 / 触发 / 买入 / 卖出 / 减仓 / 增仓 / 失效 / 复核 / 改变
```

### 带单位数字

```regex
\d+(?:\.\d+)?\s*(?:%|pp|倍|x|元|亿|万|HKD|RMB)
```

### 来源锚点

```regex
\[source:\s*([^\]]+)\]
```

---

审计原则：任何无法解释“为什么能代表报告质量”的规则，都不应因为已经写进代码就默认保留；任何容易被低成本游戏化的规则，都不应升级为发布硬门。
