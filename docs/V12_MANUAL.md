# V12.18 龟龟投资策略框架 — 使用手册

> **目标读者**：接手本项目的 AI Agent。读完本文即可开始执行分析任务，无需探索代码。
> **最后更新**：2026-08-03
> **版本历程**：... → V12.18(保守偏空校正+控股豁免+框架局限性+CSMAR全量修复+web_search启用+报告归档+定性降级+source脚注化)

---

## Part 0: 速查卡

### 框架是什么

龟龟投资策略框架（Turtle Investment Framework）是一套**全自动股票分析系统**：
- **定性**：Dayu 方法论深度分析（商业模式、护城河、治理、风险）
- **定量**：Turtle 四因子估值模型（GG 穿透回报率 + DDM 估值 + 否决门）
- **输出**：15 章买方级投资报告，所有数据断言附带 `[source: X]` 证据锚点

### 统一入口

生产运行的模型路由、预算、缓存、manifest、密钥边界和故障恢复以 [运行治理与恢复手册](RUNTIME_OPERATIONS.md) 为准。密钥继续由本地 `analyze.sh` / `.env` 提供，但这两个文件必须保持忽略状态，禁止把值写入日志或运行产物。

```bash
# V12 全模式（Dayu定性 + Turtle定量 → 15章统一报告）
# unified 默认开启来源深化和当次 run 的研究执行台账。
python -m turtle_agent.run --code 06668.HK --unified

# V11 兼容模式（仅定量）
python -m turtle_agent.run --code 06668.HK

# 仅定性分析（Ch1-Ch9）
python -m turtle_agent.run --code 06668.HK --qualitative-only

# 干跑（仅 Python 计算，不调 LLM）
python -m turtle_agent.run --code 06668.HK --dry-run

# 跳过数据准备（续跑）
python -m turtle_agent.run --code 06668.HK --skip-prepare
```

### 核心数据流

```
stock_analysis.db (8,433只股票, 2005-2025)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│ Phase 0:  前置诊断 → analysis_contract.json         │
│ Phase 0.5: 年报下载 → {year}_年报.pdf               │
│ Phase 1:  定量计算 → compute_bundle.json            │
│ Phase 1.5: 财务趋势+行业 → trends/industry json     │
│ Phase 2.1: PDF→MD → {year}_年报.md                  │
│ Phase 2.3-2.4: Zone B LLM提取 → mda/seg/risk json  │
│ Phase 3:  Zone J 参数 → moat/capex/quality json    │
│ Phase 3.5: 重算 bundle（含 Zone J 参数）            │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Agent Loop (单Agent + 19工具)                      │
│  写Ch1-Ch9定性 → 提取定性摘要 → 写Ch10-Ch13定量    │
│  → 写Ch0投资要点 → 组装报告 → 质量门禁             │
└─────────────────────────────────────────────────────┘
        │
        ▼
    {code}_分析报告_v12.md  (15章完整报告)
```

### 关键目录速查

| 路径 | 内容 |
|------|------|
| `scripts/turtle_agent/run.py` | CLI 统一入口 |
| `scripts/turtle_agent/agent_loop.py` | 核心 Agent 循环 + System Prompt 构建 |
| `scripts/turtle_agent/llm_client.py` | LLM API 客户端（Anthropic/OpenAI/DeepSeek） |
| `scripts/turtle_agent/tool_registry.py` | 工具注册与调度 |
| `scripts/turtle_agent/tools/read_tools.py` | 读取工具（8个） |
| `scripts/turtle_agent/tools/calc_tools.py` | 计算工具（6个） |
| `scripts/turtle_agent/tools/write_tools.py` | 写作+审计工具（4个） |
| `scripts/turtle_agent/tools/phase_tools.py` | Phase 执行工具（12+个） |
| `scripts/turtle_agent/tools/search_tools.py` | 网络搜索工具（2个：web_search/web_fetch） |
| `scripts/compute_bundle.py` | 定量计算引擎（~1500行，核心） |
| `scripts/pre_analysis_phase.py` | Phase 0 前置诊断 |
| `scripts/zone_b_v8.py` | Zone B 定性提取（960行） |
| `scripts/zone_j_agent.py` | Zone J 判断参数（4 Agent 并行） |
| `scripts/zone_d_industry_context.py` | 行业对比（纯 SQL） |
| `scripts/build_financial_trends.py` | 财务趋势提取 |
| `scripts/pdf_preprocessor.py` | PDF 内容提取+Markdown转换 |
| `scripts/download_report.py` | 三市场年报下载（A股/港股/美股） |
| `templates/report_template_v12.md` | V12 报告模板（2740行） |
| `stock_analysis.db` | 核心数据库（~8K股票） |
| `output/{code}_*/` | 各股票分析输出目录 |

---

## Part 1: 架构总览

### 6 Phase 流水线

```
Phase 0:  前置诊断（pre_analysis_phase.py）
          输入: stock_analysis.db
          输出: analysis_contract.json
          内容: 断点检测（商誉跳升>20%总资产、资产跳升>50%且收入脱钩<30%）
                + 双维度周期分类（供给CV×需求驱动）
                + 动态分析窗口（强周期10年, 弱周期5年, 成长股强制5年）
                + 三轨权重配置

Phase 0.5: 年报下载（download_report.py）
          输入: analysis_contract.json 的 effective_years
          输出: {year}_年报.pdf（多份）
          来源: cninfo（A股巨潮，分类API+修订版优先+财年正则推断）
                + hkexnews（港股披露易，titleSearchServlet API+stockId解析）
                + SEC EDGAR（美股，ticker→CIK→submissions→index.json）

Phase 1:  定量计算（compute_bundle.py --from-db --contract）
          输入: stock_analysis.db + analysis_contract.json
          输出: compute_bundle.json
          内容: Factor2(粗算GG: R(NP), R(OE), M系数, OCF/NP质量, 否决门)
                + Factor3(精算GG: AA序列7步构建, 少数股东调整, g_adj, GG三档,
                          HH偏离检测, AP伪现金流检测, λ临界收入倍数)
                + Factor4(DDM估值: 公允价, 五档阶梯买入价, 价值陷阱7项检测,
                          仓位建议, 止损)

Phase 1.5: 辅助数据（build_financial_trends.py + zone_d_industry_context.py）
          输入: stock_analysis.db
          输出: financial_trends.json（三表多年趋势+CAGR+利润率）
                + industry_context.json（同行百分位+可比同行列表+信号）

Phase 2.1: PDF处理（pdf_preprocessor.py → 全量Markdown）
          输入: {year}_年报.pdf
          输出: {year}_年报.md（全量）+ pdf_sections_{year}.json（10类结构化）
          纯Python, 不需要LLM。使用pdfplumber+PyMuPDF fallback，
          含乱码检测（CJK重复率>5%或非正常字符>30%时触发PyMuPDF）。

Phase 2.3-2.4: Zone B 定性提取（zone_b_v8.py）
          输入: {year}_年报.md + financial_trends.json（DB财务上下文嵌入prompt）
          输出: mda.json, segments.json, risks.json, governance.json, audit.json
          方式: 每年一个LLM提取（从markdown，取前50K chars）
                → 纯Python聚合（aggregate_partials_to_zone_b，零信息丢失）

Phase 3:  Zone J 判断参数（zone_j_agent.py）
          输入: Zone A/B JSON + qualitative_summary.json（如存在）
          输出: moat_assessment.json(护城河证据+b_penalty+g_base)
                capex_classification.json(Capex类型+mcapex_split_pct+增量ROIC)
                earnings_quality.json(AR质量+AP检测+非经常项目+OCF质量)
                data_discount.json(折价因素+总折价率5-25%)
                governance_tension.json(少数股东结构+双重身份+分红决策权+治理折价0-10%, V12.15新增)
          方式: 5个LLM Agent并行（ThreadPoolExecutor, max_workers=5）
                每个Agent有allowed_inputs白名单+prompt_template

Phase 3.5: 重算（compute_bundle.py --zone-j）
          输入: compute_bundle.json + Zone J JSONs
          输出: compute_bundle.json（更新, 含折价后GG_discounted）
```

### Python vs LLM 分工原则

| Python 负责（标准化加工，不需要判断） | LLM 负责（需要商业判断的转化） |
|---|---|
| 会计数据提取与统计加工 | 护城河评级与证据链构建 |
| 财务比率计算（ROE/毛利率/OCF/NP） | 商业模式叙事构建 |
| 同行百分位排名（纯SQL） | 管理层讨论的定性洞察提取 |
| PDF 文本提取 + Markdown 转换 | Zone J 参数的证据锚定与推理 |
| Zone B 年度数据的 Python 聚合 | 章节内容写作与自修复 |
| 审计规则检查（S1/E1/C1/C2） | 增长分类判断 |

**数据来源分工**：定量数据一律走 `stock_analysis.db`（annual_financials 表），PDF 只提供定性叙事（管理层讨论、风险描述、治理结构、审计意见、分部经营分析）。`compute_bundle.py` / GG / DDM 的数据源是 DB，不依赖 PDF 提取的数字。

---

## Part 2: 数据体系

### 2.1 stock_analysis.db — 核心数据库（三数据源）

**路径**：`{框架根目录}/stock_analysis.db`
**规模**：~8,700 只股票（A股 5,559 + 港股 3,161），159K 行，2000-2025

| 数据源 | 市场 | 年份 | 来源 |
|--------|------|------|------|
| CSMAR A股面板 | A股 (000001.SZ, 600519.SH...) | 2000-2025 | `cn_financials_panel_raw/` — 利润表+BS+CF(直接法/间接法)+分红+基本信息 |
| CSMAR HK | 港股 (00700.HK, 00506.HK...) | 2005-2025 | `hk_new_financials/` — 利润表(金融/非金融)+BS(金融/非金融)+CF+披露指标 |
| Tushare HK (legacy) | 港股 | 2005-2025 | `hk_financials/` — 已迁移至 DB，由 CSMAR HK 补充 |

**核心表结构**：

| 表名 | 关键字段 | 用途 |
|------|---------|------|
| `stocks` | ts_code, name_cn, name_en, market, listing_date, shares_m, currency | 股票元信息 |
| `annual_financials` | ts_code, fiscal_year, report_type, **200+ REAL 列**（含 revenue, n_income_attr_p, n_cashflow_act, c_pay_acq_const_fiolta, d_a, money_cap, accounts_receiv, total_assets, total_liab, total_hldr_eqy_exc_min_int, goodwill, st_borr, lt_borr, invest_income, admin_exp, sell_dist_exp, fix_assets, intang_assets, inventories, cash_paid_employees, dividends_paid, dps, base_share, surplus_reserve, capital_reserve...） | 所有财务计算 |
| `industry_classification` | ts_code, industry_l1, industry_l2 | 行业分类 |
| `thresholds` | ts_code, II (门槛回报率%), star_5, star_4, star_3, category, rationale | 估值阈值 |
| `financial_observations` | ts_code, fiscal_year, field_name, normalized_value, source_type, confidence | 细粒度数据观测 |
| `quality_findings` | ts_code, field_name, severity (BLOCK/WARN), fix_status | 数据质量标记 |

**关键字段覆盖**（全市场 159K 行）：

| 字段 | 覆盖 | AA 用途 |
|------|------|---------|
| `cash_paid_employees` | 73K 行 (A股 ✅, HK 171只) | **W2 L1 真实现金** |
| `admin_exp` + `sell_dist_exp` | 147K+ 行 (全市场 ✅) | **W2 L3 SG&A代理** |
| `invest_income` | 95K 行 | Step 3 V5 投资收入 |
| `dividends_paid` | 25K 行 (HK) + A股 | M 系数 |
| `dps` | 26K 行 (HK) + A股 | M 系数 / DDM |
| `d_a` | 51K 行 (HK) + A股 | 所有者盈余 |

**所有金额单位为百万元 RMB**。CSMAR 原始数据为元，导入时自动 ÷1,000,000。**所有 NULL 已归零**——Agent 看到 0 即表示"该项目为零或未披露"。

### 2.2 Zone A — 定量 JSON

| 文件 | 生成脚本 | 主要内容 |
|------|---------|---------|
| `compute_bundle.json` | compute_bundle.py | factor2(粗算GG: R(NP)/R(OE)/M/OCF_NP/否决), factor3(精算GG: AA逐年序列/AA₃y/g_adj/GG三档/HH偏离/λ/gg_discounted), factor4(DDM: 公允价HKD+RMB/tiers五档/止损/价值陷阱), params(II/Rf/Q/g_base/b_penalty), market(股价/股本/市值/FX), rejection_summary, calculation_trace |
| `financial_trends.json` | build_financial_trends.py | income/balance_sheet/cashflow/per_share 多年趋势 + CAGR(3y/5y/all) + profitability_ratios(ROE/ROA/margin) |
| `industry_context.json` | zone_d_industry_context.py | comparable_peers(前5营收最接近同行), percentiles(各指标百分位排名), signals(STRENGTH≥P80/WEAKNESS≤P30) |
| `analysis_contract.json` | pre_analysis_phase.py | effective_years, cycle_type, breakpoints, analysis_start_year, three_track_config, cyclicality_profile |

### 2.3 Zone B — 定性 JSON（LLM 预提取）

| 文件 | 内容 |
|------|------|
| `mda.json` | year_highlights, mgmt_explanations, forward_guidance, strategy_changes, key_operations_metrics, mda_key_financials (来自DB), trend_analysis(毛利率趋势/营收质量/战略执行) |
| `segments.json` | 各年分部收入, revenue_structure_evolution, margin_by_segment_trend |
| `risks.json` | principal_risks, risk_evolution, goodwill_trend, contingent_liabilities, ar_aging |
| `governance.json` | related_party_transactions, governance_timeline, transparency_assessment |
| `audit.json` | auditor_history, audit_opinion_history, key_audit_matters, non_recurring_summary, accounting_policy_changes |

**薄数据检测**：`agent_loop.py:_load_context()` 会检查 Zone B 文件是否内容全空（所有值都是 "⚠️ 无提取数据" 或空数组）。若检测到薄数据，标记 `_thin: True` 并视为缺失——Agent 需用 `read_section` 直接读 PDF。

### 2.4 Zone J — 判断参数 JSON

| 文件 | 关键字段 |
|------|---------|
| `moat_assessment.json` | moat_evidence（含type/evidence/quote/durability）, b_class_segments, b_penalty_final(0.0-0.5，含rationale+evidence_ref+confidence), g_base(1.0-4.0%), g_scenarios, value_trap_signals |
| `capex_classification.json` | capex_type(light/heavy/mixed), mcapex_split_pct(维持性Capex占比), growth_classification(A/B/C), incremental_roic |
| `earnings_quality.json` | ar_quality(collection_ratios+adjustment), ap_excess_check, non_recurring_items(keep/exclude), ocf_quality_flags |
| `data_discount.json` | discount_factors, total_discount_pct(5-25%), confidence_by_section(factor2/3/4) |
| `governance_tension.json` | minority_structure, dividend_decision_power, conflict_of_interest, governance_discount(0-10%), V12.15新增 |

Zone J 每个参数必须附带 `evidence_ref`（指向 Zone B JSON 的具体字段）、`rationale`、`confidence`。**moat_rating 明确禁止在 Zone J 输出**——那是 Zone C（Agent Loop 定性写作）的职责。

**职责边界补充**：Zone J 可以提示 DB proxy 可能失真、建议触发 PDF extraction、输出折价/分类/解释；**不能直接产出或覆盖 GG 核心数值**。GG 的最终数值只能由 `compute_bundle.py` 按固定优先级计算。

### 2.5 年报文件

- `{year}_年报.pdf` — 原始年报 PDF
- `{year}_年报.md` — 全量 Markdown 转换（`pdf_preprocessor.extract_all_pages()`，纯 Python，含 table→markdown）
- `page_map_{year}.json` — 章节页码导航（`pdf_page_locator.py` 生成，用于 `read_section` 快速随机访问）
- `pdf_sections_{year}.json` — 10 类章节（MDA/SEG/STMT/DAN/P2/P3/P4/P6/P13/SUB）的结构化文本 + regex财务数字

### 2.6 数据可用性层级

```
可信度从高到低：
1. stock_analysis.db（CSMAR/Tushare 财务数据）— 最高可信度，所有 NULL=0
2. PDF 年报原文（公司官方披露）— 高可信度
3. Zone B JSON（LLM 预提取结构化洞察）— 中高可信度
4. web_search / web_fetch（DuckDuckGo 免费搜索，V12.17 新增）— 中低可信度
```

**规则**：
- Web 搜索结果不能覆盖 DB 或年报数据。若冲突，以 DB/年报为准
- `web_search` 用于行业新闻、竞争动态、最新事件 — DB 和年报里没有的内容
- 财务数据/股价/分红 — DB 已有，不要用 web_search 浪费 token
- 网络数据引用格式：`[source: web_search → {域名} {日期}]`

### 2.7 AA W2 员工成本四层回退

AA 计算 Step 4(经营支出 W) 的 W2 员工成本按以下优先级取数：

| 优先级 | 数据源 | 覆盖范围 | 可靠性 |
|--------|--------|---------|--------|
| **L1** | `cash_paid_employees` (CSMAR CF直接法-支付给职工) | A股 72K 行, HK 171只 | ⭐⭐⭐ 真实现金 |
| **L2** | `employee_cost` (DB列) | 暂无 | — |
| **L3** | `admin_exp + sell_dist_exp` (SG&A代理) | 全市场 147K 行 | ⭐⭐ 合理近似 |
| **L4** | 倒挤法 = rev - OCF + interest + tax | 纯 fallback | ⭐ 最后手段 |

A股 93% 走到 L1（真实现金数据），港股主要走 L3（SG&A代理）。港交所不强制披露直接法 CF 及单独列示员工成本，这是数据源结构差异，非数据缺失。

---

## Part 3: Agent 工具手册

V12 Agent 拥有 **19+ 个工具**，分为 4 个模块。Agent 通过 LLM function calling 按需调用。所有工具返回 `{"ok": bool, "value": ...}` 或 `{"ok": bool, "error": str}`，**永不抛异常**。

### 3.1 工具总表

| # | 工具名 | 模块 | 用途 | 关键参数 |
|---|--------|------|------|---------|
| 1 | `list_documents` | read | 列出可用文档和JSON | output_dir |
| 2 | `read_section` | read | 读年报特定章节文本 | output_dir, year, section(MDA/RISK/GOV/AUDIT/STMT/NOTES/SEG), max_chars |
| 3 | `search_report` | read | 年报全文关键词搜索 | output_dir, query, year(可选) |
| 4 | `get_financial_statement` | read | 获取标准化财报数据 | output_dir, statement_type(income/balance_sheet/cash_flow/overview) |
| 5 | `read_zone_data` | read | 读Zone B定性JSON | output_dir, zone(mda/segments/risks/governance/audit) |
| 6 | `get_financial_trends` | read | 获取多年财务趋势 | output_dir |
| 7 | `get_peer_comparison` | read | 同行对比+百分位排名 | output_dir |
| 8 | `get_market_data` | read | 市场数据+股本可信度警告 | output_dir |
| 8b | `get_global_benchmarks` | read | 国际对标公司数据（V12.15新增） | output_dir |
| 9 | `compute_gg` | calc | 计算穿透回报率GG | output_dir |
| 10 | `compute_aa` | calc | AA 7步构建链路展示 | output_dir |
| 11 | `compute_ddm` | calc | DDM估值+tiers | output_dir |
| 12 | `assess_moat` | calc | 护城河评级(从Zone J) | output_dir |
| 13 | `evaluate_decision` | calc | 综合决策(Continue/Hold/Abandon) | output_dir |
| 14 | `compute_data_quality` | calc | 数据完整性评估 | output_dir |
| 15 | `write_chapter` | write | 写入章节(含自动审计) | output_dir, chapter_index, title, content |
| 16 | `read_chapter` | write | 读取已写章节 | output_dir, chapter_index |
| 17 | `audit_chapter` | write | 审计指定章节 | output_dir, chapter_index |
| 18 | `assemble_report` | write | 组装最终报告+质量门禁 | output_dir, company_name, ts_code |
| 19 | `run_pre_analysis` | phase | Phase 0前置诊断 | code, output_dir |

另有 `download_annual_reports`、`check_report_completeness`、`compute_bundle_db`、`extract_pdf_sections`、`verify_report` 等 Phase 工具通过 `auto_discover` 自动注册。

### 3.2 读取工具详解

**`list_documents`** — Agent 的第一步操作。返回目录下所有 PDF、JSON、`_ch*.md` 章节文件、`page_map*.json`。

**`read_section`** — 读年报章节。优先使用 page_map（页级随机访问，快），无 page_map 时全扫 PDF（前50页） + 关键词定位（中英双语）。章节标签：`MDA`/`RISK`/`GOV`/`AUDIT`/`STMT`/`NOTES`/`SEG`。max_chars 默认 30000。返回 `{section, year, text, page_range, char_count, source}`。

**`read_zone_data`** — 读 Zone B 预提取的结构化洞察。**Agent 写定性章时应优先调用此工具**，信息密度远高于原始 PDF。若返回数据包含 "⚠️ 无提取数据" 标记，说明该 zone 的 LLM 提取失败，需回退到 `read_section`。

**`get_peer_comparison`** (V12.17 强化) — 从 `industry_context.json` 提取完整同业对比数据。Agent 写 Ch2/Ch3/Ch5 前**必须调用**。返回：行业名称、目标公司指标、12 项百分位排名（含 oper_margin/net_margin/roa/debt_ratio/ocf_np/turnover/div_yield）、≥4 家同行的完整财务数据（可直接构建对比表）、STRENGTH/WEAKNESS 信号。关键原则：**行业对比数据服务于"判断分岔点"**——公司跟行业中位数哪里不同、为什么不同。

**`get_market_data`** — 获取市场数据并标注 yfinance 股本数据可信度。**港股 yfinance 常见 bug**：返回自由流通股而非总股本，导致市值被低估。此工具自动从 `stock_analysis.db` 获取正确股本并标注 `shares_m_corrected` 和 `mc_hkd_corrected`。GG 计算前必须调用此工具检查股本。

**`get_global_benchmarks`** (V12.15 新增) — 获取国际对标公司数据。从 `config/global_benchmarks.json` 匹配公司的业务关键词（装瓶商、连锁餐饮等），返回国际可比同行的关键指标（毛利率、净利率、派息率、Capex/收入、ROE）。Agent 写 Ch2 前**必须调用**。若返回 `matched=false`，跳过国际对标。若 `matched=true`，必须在 Ch2 中构建 ≥3 家国际同行 × ≥4 项指标的对比表，分析中国公司的结构性折价/溢价来源。

### 3.3 计算工具详解

**`compute_gg`** — 核心估值工具。返回完整的 GG 计算链路：
- `ingredients`：NP_avg_3y / OE_avg_3y / AA_avg_3y / M(含source+samples+warning) / Q / MC(含corrected标记) / g_adj
- `r_np_pre_tax` / `r_oe_pre_tax`：因子2 粗算结果
- `gg_base` / `gg_pessimistic` / `gg_optimistic`：因子3 精算三档
- `hh` / `hh_note`：HH 偏离检测（|R(NP)-GG|）
  - >3pp → "因子2不适用，以精算GG为准"
  - >1.5pp → "因子2可信度存疑"
  - ≤1.5pp → "因子2与因子3一致"
- `implied_pe`：隐含PE = 100/GG
- **自动修正 yfinance 股本错误**：若 shares_warning=true，从 DB 获取真实股本并重算 R(NP)/GG
- **自动从 DPS/EPS 计算真实 M 值**：若 M 来源为 fallback，尝试从 financial_trends.json 计算实际支付率

**`compute_aa`** — 展示 AA（可支配现金结余）的完整 7 步构建链路（对标海螺水泥报告深度）：
- **Step 1**: 真实现金收入还原 — S - ΔAR↑ - ΔContract↓（剔除应收账款变动和合同负债变动对收入的扭曲）
- **Step 2**: 数据分类提取 — 从 DB 提取 inc/bs/cf 各科目（revenue, OCF, Capex, AR, AP, contract_liab, D&A 等）
- **Step 3**: V（非经常性项目）分类 — V1资产处置 + V2-V4政府补助/保险/一次性扣除 + V5投资收入（利息+其他收入）
- **Step 4**: W（经营支出，现金口径）— 用 revenue - OCF + interest_paid + tax_paid 近似（避免权责发生制与现金制混用）。若计算异常（W>95%或<50% revenue），回退到保守默认85%
- **Step 5**: Y（资本支出）— Capex(E) + 投资购买无形资产(X1) + 隐性支出(X2默认0)。mcapex_split_pct 来自 Zone J capex_classification，默认1.0（全额视为维持性）
- **Step 6**: 少数股东权益调整 — 当少数股东损益 > 合并净利润10%时触发。AA按归母比例（parent_ratio_3y）折算：合并OCF含少数股东现金流，归母股东无法支配该部分
- **Step 7**: 年度结余 — 真实现金收入 + V1 + V5 - V_deduct - W - Y。取正值（不低于0），计算3年均值 → AA₃y

额外返回：
- `aa_annual`：逐年 FCF 数据
- `receipt_ratios`：逐年收款比率（真实现金收入/报表收入）
- `ap_driven_analysis`：AP 驱动伪现金流拆解（若 DPO 持续拉长，计算超额AP → ap_pct → ap_adjusted_aa）
- `net_cash` / `net_cash_pct_mc`：净现金及占市值比

**`compute_ddm`** — DDM 估值。返回公允价（HKD/RMB）、五档阶梯买入价（5星60%→1星100%公允价）、安全边际%、止损建议（硬止损HKD/基本面/时间/事件）、价值陷阱检测（7项标准）、隐含PE。

**`evaluate_decision`** — 基于规则的决策引擎：
- GG < II × 0.5 → Abandon (high confidence)
- GG > II + upside≥30% + no value trap → Continue (high)
- GG > II but upside<30% → Continue (medium)
- GG near II → Hold
- GG 不可用（净现金/MC 过高或股本异常）→ Hold (low)，需手动评估
- 事后一致性验证（`decision_synthesizer.validate_decision`）

**`compute_data_quality`** — 统计 Zone A(3文件)/B(5文件)/J(4文件) 覆盖率。对标"海螺水泥 36/36字段，0%折价"。给出折价建议：100%→0%, ≥80%→5-10%, ≥60%→10-15%, <60%→15-25%。

### 3.4 写作工具详解

**`write_chapter`** — 写一章到 `_ch{XX}.md`。自动运行可编程审计（S1占位符/E1证据密度/C2禁止项），审计结果附带在返回值中。同时记录到 `_tracker.json`（ExecutionTracker）。

**`audit_chapter`** — 独立审计已写章节。调用 `audit_rules.run_audit()`，返回 violations 列表（每条含 rule_code/severity/description）、error_count、warn_count、passed 布尔值、verdict (pass/regenerate/patch)、repair_plan。

**`assemble_report`** — 组装最终报告 + 运行全套质量门禁：
1. 拼接所有 `_ch*.md` → `{code}_分析报告_v12.md`
2. 构建来源清单（`source_list_builder.py`，按来源文件去重聚合）
3. 质量检查：`quality_gate` → `evidence_citation` → Zone B使用率 → `enhanced_quality_gate` → `data_gap_scanner`
4. **事实对账器**（V12 核心机制）：正则提取报告中的 GG/DPO/M 等关键数字，与 `compute_gg`/`compute_aa` 工具结果交叉验证。发现矛盾 → 返回 warning
5. 行数检查：<800行 → 失败，<2000行 → 警告（建议≥3000行）

### 3.5 典型工具调用顺序

```
Agent 启动 →
 1. list_documents              → 了解可用数据全貌
 2. get_peer_comparison         → 同行对比（写Ch2/Ch3前必须）
 3. get_financial_trends        → 财务趋势概览
 4. get_market_data             → 市场数据（检查股本可信度！）
 5. read_zone_data(mda)         → 管理层讨论（写Ch1/3/4/5前）
 6. read_zone_data(segments)    → 分部报告（写Ch1/2前）
 7. read_zone_data(risks)       → 风险因素（写Ch7前）
 8. read_zone_data(governance)  → 治理数据（写Ch8前）
 9. read_zone_data(audit)       → 审计数据（写Ch9前）
10. compute_gg                  → GG计算（写Ch11前）
11. compute_aa                  → AA 7步构建（写Ch11前，展示推导）
12. compute_ddm                 → DDM估值（写Ch12前）
13. compute_data_quality        → 数据完整性得分
14. assess_moat                 → 护城河评级
15. write_chapter (×13+)        → 逐章写作+即时审计
16. evaluate_decision           → 综合决策（写Ch13前）
17. assemble_report             → 最终组装+质量门禁+事实对账
```

---

## Part 4: 报告模板体系

### 4.1 模板结构

`templates/report_template_v12.md`（2740行）定义了 15 章结构：

```
Ch0: 投资要点概览 — 封面页（最后写，综合全部分析）
Part A: 定性深度分析（Dayu 方法论）
  Ch1:  公司做的是什么生意
  Ch2:  行业吸引力与公司位置
  Ch3:  商业模式机制、护城河与关键约束
  Ch4:  最近一年关键变化与当前阶段
  Ch5:  经营表现与核心驱动
  Ch6:  财务表现与资本配置
  Ch7:  股东回报路径
  Ch8:  管理层、治理与激励
  Ch9:  核心风险与否决项
Part B: 量化投资判断（Turtle 四因子模型）
  Ch10: 增长质量与参数校准
  Ch11: 穿透回报率 GG
  Ch12: DDM 估值与仓位建议
Part C: 综合决策
  Ch13: 综合决策（5状态合成矩阵）
来源清单（自动聚合）
```

### 4.2 HTML 注释合约系统

模板中的 `<!-- ... -->` 注释块是**可编程合约**，定义了每章的写作约束。由 `template_parser.py` 解析。

**合约类型**：

| 合约 | 用途 |
|------|------|
| `REPORT_GOAL` | 全文目标（买方全貌分析报告） |
| `AUDIENCE_PROFILE` | 目标受众（买方分析师/基金经理） |
| `COMPANY_FACET_CATALOG` | 36种业务类型 + 25种约束条件候选集 |
| `CHAPTER_GOAL` | 本章一句话核心目的 |
| `CHAPTER_CONTRACT` | 完整写作契约（含 must_answer/must_not_cover/required_output_items/preferred_lens） |
| `ITEM_RULE` | 条件性内容规则（mode/when/facets_any/item） |

**CHAPTER_CONTRACT 字段**：
- **`narrative_mode`**：叙事模式（如 "结构化分析（逐项展开，每小节至少3段叙述+1张表格）"）
- **`must_answer`**：必须回答的问题列表（Agent 必须逐一覆盖）
- **`must_not_cover`**：禁止覆盖的内容（防止章节内容越界。如 Ch1 禁止展开竞争格局、市场份额、护城河强弱判断）
- **`required_output_items`**：必须输出的条目（不可缺项）
- **`preferred_lens`**：推荐的认知口径，每个 lens 可绑定：
  - `facets_any`：匹配的公司 facet 标签列表（条件触发）
  - `priority`：`core`（核心口径）或 `supporting`（辅助口径）

**ITEM_RULE 字段**：
- **`mode`**：`optional`（有稳定披露就写）或 `conditional`（条件成立才写）
- **`when`**：触发条件的人类语言描述
- **`facets_any`**：公司匹配的 facet 标签列表（与 COMPANY_FACET_CATALOG 交叉匹配）
- **`item`**：应输出的内容条目名称

**Agent 写每章前的标准流程**：
1. 读该章所有 ITEM_RULE，逐个检查 `when` 条件
2. 不确定 → 调用工具验证（如 `net_cash_pct_mc > 100%` → 调 `compute_aa`）
3. 成立 → 写入该条目；不成立 → 跳过，不解释不占位
4. 再读该章的 preferred_lens，匹配公司 facet 的优先采用

### 4.3 Facet 系统

**36 种 business_model_candidates**（业务类型）：
平台互联网、电商/交易平台、广告媒体、内容/娱乐平台、游戏/互动娱乐、企业软件、垂直软件/创意软件、数据基础设施/数据中心、支付/金融基础设施、交易所/市场基础设施、资产管理/财富管理、银行、消费金融/信贷、保险、硬件/消费电子、半导体设计、半导体设备/制造、整车制造、汽车零部件、动力电池/关键部件、工业制造/关键部件、特种材料/配方材料、大宗材料/基础化工、物流网络/快递、航空/航运/出行服务、REIT/基础设施、公用事业、通信/连接服务、医疗器械、生命科学工具、生物制药、医疗服务、上游资源/勘探开发、能源设备/服务、酒店/旅游服务、消费品牌、零售渠道/连锁

**25 种 constraint_candidates**（约束条件）：
监管敏感、出口限制敏感、数据/隐私敏感、许可/牌照依赖、高资本开支、高研发驱动、高营销费用驱动、高SBC、高负债/融资依赖、利率敏感、周期性强、商品价格敏感、专利/管线依赖、支付方/报销方依赖、单一关键供应商依赖、客户集中、单一产品/资产集中、渠道/分发依赖、网络效应显著、规模效应显著、品牌效应明显、有明显定价权、关联交易风险、多归属/低切换成本风险、预收款/合同负债敏感、利用率敏感、项目制/长交付周期

**Agent 写作前应根据 financial_trends.json 和 segments.json 判断公司主业务类型（1-3个 primary facets）和关键约束（1-3个 cross-cutting facets），然后在章节中优先使用匹配的 preferred_lens**。

### 4.4 章节标准结构

每章必须包含三部分，不能多也不能少：
```
### 结论要点        ← bullet 简明扼要，30秒抓住核心
### 详细情况        ← #### 四级标题分隔子节，至少2-3段叙述+表格
### 证据与出处      ← 表格列出所有来源及其关键数据
```

**Bullet 格式要求**：bullet 下另起一行输出回答，不留空行。禁止写成 `- 标签：回答` 格式。相邻 bullet 之间保留空行。禁止数字编号。

---

## Part 5: 核心方法论 — Turtle 四因子模型

### 5.1 因子总览

| 因子 | 名称 | 核心指标 | 用途 |
|------|------|---------|------|
| Factor 1 | 资产质量与商业模式 | 护城河评级、b_penalty、g_base | 定性判断，通过 g_adj 影响因子3 |
| Factor 2 | 粗算穿透回报率 | R(NP) = NP₃y×M×(1-Q)/MC, R(OE) = OE₃y×M×(1-Q)/MC, OCF/NP质量 | 基准对比，HH偏离检测 |
| Factor 3 | 精算穿透回报率 GG | GG = AA₃y × M × (1-Q) / MC × 100 | **核心决策指标** |
| Factor 4 | DDM 估值 + P_base 目标价 | 公允价 = DPS × (1+g) / (II-g), P_base = MC×(GG/II)/shares | 安全边际、阶梯买入价 |

### 5.2 GG 计算公式 (V12.5 更新)

```
因子2 粗算（两个口径）：
  裸 NP 收益率（诊断用）：
    R(NP)_raw = NP_avg_3y / MC_rmb × 100
  穿透回报率（与精算GG同单位，Spec Factor2 Step8）：
    R(NP)_penetration = NP_avg_3y × M × (1-Q) / MC_rmb × 100
    R(OE)_penetration = OE_avg_3y × M × (1-Q) / MC_rmb × 100
  否决门使用穿透回报率（V12.5 FIX）

因子3 精算：
  GG = AA_avg_3y × M × (1-Q) / MC_rmb × 100

  其中：
    AA_avg_3y = 近3年可支配现金结余均值（7步构建，见5.3）
    M = 分红支付率（四层推断：DPS/EPS数据 > 现金流分红/净利润 > 行业默认0.7）
    Q = 股息税率（默认0.10）
    MC_rmb = 市值（百万元 RMB）
```

**HH 偏离检测** (V12.5 FIX)：`|R(NP)_penetration - GG|`
- 现在使用穿透 R(NP)（含 M×(1-Q)）而非裸 R(NP)，两者同单位
- > 2pp → 因子2粗算不适用，以精算 GG 为准
- > 1.5pp → 因子2可信度存疑，标注差异来源（纯由 NP vs AA 的权责发生制vs现金制差异导致）
- ≤ 1.5pp → 因子2与因子3一致

### 5.2b 三种 GG 视角 (V12.13 新增)

不同商业模式适用不同的 GG 计算路径。框架提供三种视角，Agent 根据公司特征选择主视角：

```
1. AA GG（保守，默认）
   GG = AA_avg × M × (1-Q) / MC
   AA 通过 7 步构建（全额扣 Capex + W 倒挤法 + 少数股东调整）
   适用：大多数公司。最保守的口径。

2. FCFE GG（现实，绕开 W）
   FCFE = (OCF - Capex) × 归母比例
   GG = FCFE × M × (1-Q) / MC
   适用：高 OCF/NP、低 OCF/Rev 公司（装瓶商、贸易商）。
   AA GG 过于保守时（如 00506 AA=3.5% vs FCFE=6.4%），FCFE 更贴近经济实质。

3. Normalized GG（正常化，只扣维持 Capex）
   AA_norm = AA_conservative + (full_capex - D&A×G_coef)
   GG = AA_norm × M × (1-Q) / MC
   适用：低 Capex 公司。当实际 Capex < 维持 Capex 时无效。
```

**Agent 判断规则**：当三种 GG 分歧 > 2pp 时，在 Ch11 中显式标注分歧来源（W 倒挤法 / 少数股东 / Capex），不机械取平均值。

**治理折价叠加** (V12.15 新增)：当 Zone J `governance_tension.json` 存在且 `governance_discount.additional_discount_pct > 0` 时，治理折价叠加到 `data_discount` 上：`total_discount = data_discount + governance_discount`。`gg_discounted` 反映两层折价后的 GG。治理折价反映少数股东双重身份、分红决策障碍等结构性风险，上限 10%。

### 5.2c EV 双轨 (V12.5 新增)

当 `净现金/市值 > 40%` 时自动触发——高现金公司用剔除现金后的 EV（企业价值）做分母：

```
EV = MC_rmb - 净现金（max(0, money_cap - total_liab)）
GG_EV = AA_avg_3y × M × (1-Q) / EV × 100

含义：账上现金远超运营需要时，MC口径的GG会被现金"稀释"而偏低。
      EV口径反映剔除冗余现金后的真实经营回报率。
```

输出到 `compute_bundle.json` 的 `factor3.gg_ev`。

### 5.2c λ 收入敏感性分析 (V12.5 新增)

```
λ = median(ΔAA / ΔS) over 3 years  — 每1元收入变动→可支配现金变动

临界收入倍数 = 解 GG=II 时的收入 / 当前收入
  - ≥ 0.85 → ⚠️ 敏感（收入小幅下滑GG即跌破II）
  - 0.7-0.85 → 中等韧性
  - < 0.7 → 韧性强
```

输出到 `compute_bundle.json` 的 `factor3.lambda_sensitivity`。

### 5.2d 外推可信度 5 维评级 (V12.5 新增)

| 维度 | 可计算？ | 阈值 |
|------|---------|------|
| ① 收入波动率（5y CV） | ✅ | <10% high, 10-25% medium, >25% low |
| ② 利润调整偏差 | ⚠️ 需Zone J | 默认high，由earnings_quality覆盖 |
| ③ HH偏离 | ✅ | <1pp high, 1-3pp medium, >3pp low |
| ④ 商业模式变化 | ⚠️ 需定性 | 默认high，需Ch4定性确认 |
| ⑤ λ 可靠性 | ✅ | ΔAA/ΔS同号 high, 异号 low |

总体评级：≥4 high → high, ≥2 low → low, 其他 → medium。输出到 `compute_bundle.json` 的 `factor3.extrapolation_rating`。

### 5.2e P_base 目标价 (V12.5 新增)

```
P_base = MC × (GG/II) / shares  — 在此价格下GG恰好等于II

P_EV = (NetCash + EV × GG_EV / II) / shares  — EV双轨版（仅EV触发时）
```

输出到 `compute_bundle.json` 的 `factor4.p_base`。若存在 FCFE GG，同时输出 `p_base.p_fcfe` 作为参考视角（少数股东重公司更有参考价值）。

### 5.2f GG 数据源分层与 Override 机制 (V12.16 新增)

GG 的最终计算器始终是 `compute_bundle.py`。框架承认一个现实：DB 可以稳定提供总量财务数据，但**无法普遍精确拆分“直接人工 vs 管理人工 vs 外包服务成本”**。因此，GG 对人工拆分敏感的行业必须采用分层数据源，而不是把会计重构交给 Zone J 或写报告时的 Agent 即兴判断。

**原则**：
- `stock_analysis.db` 仍是 GG 的默认定量来源，保证可复现。
- `cash_paid_employees`、`admin_exp`、`sell_dist_exp` 只是 proxy，不是附注级事实。
- Agent 可以参与**事实抽取**，不能直接成为 GG 的最终数值计算器。
- `report agent` 只消费 `compute_bundle.json` 的最终结果和依据，不自行重算 GG。

**固定优先级**：

```text
1. pdf_override
2. industry_heuristic
3. db_proxy
```

含义如下：
- `pdf_override`：来自年报 PDF 附注的结构化事实，优先级最高。适用于已能从附注中确认职工薪酬按职能拆分、外包服务成本等情形。
- `industry_heuristic`：行业保守估计层。只作为兜底，不宣称精确拆分。
- `db_proxy`：现有纯 DB 路径，例如 `cash_paid_employees - admin_exp - sell_dist_exp`，本质是代理估计。

**Override 载体**：
- 推荐文件名：`gg_override.json`
- 放置位置：与 `compute_bundle.json` 同目录
- 职责：只承接 PDF/附注抽取出的结构化事实，不直接承接最终 GG 结论

建议最小字段：
- `direct_labor_cost`
- `admin_labor_cost`
- `sales_labor_cost`
- `outsourced_service_cost`
- `notes_basis`
- `confidence`
- `source_year`
- `source_pages`

**输出透明化要求**：`compute_bundle.json` 在 GG 相关字段旁必须暴露方法元信息，至少包括：
- `gg_labor_source`
- `gg_labor_confidence`
- `gg_labor_method`
- `gg_labor_explanation`

这样报告层才能区分：
- 这是附注确认后的较高置信度结论
- 还是行业/数据库代理法下的保守估计

**行业边界**：
- 制造业、标准工业：通常可接受 `db_proxy` 或现有 AA/FCFE 路径
- 物业、劳务外包、服务密集行业：若 GG 对人工拆分敏感，应优先触发 `pdf_override`
- 若 override 缺失，则允许继续用 proxy，但必须将结果标记为估计值，而不是精确拆分

一句话原则：**Agent 负责取证，`compute_bundle.py` 负责结算，Zone J 负责提醒和解释。**

### 5.3 AA 7 步构建（核心算法）

AA（可支配现金结余，Available Appropriation）是 GG 精算的核心输入，采用**极端保守**口径。来自 `compute_bundle.py` 的 `compute_factor3()` 函数，官方 Spec Factor3 Steps 1-7：

```
Step 1: 真实现金收入还原
  真实现金收入 = 报表收入 - max(0, Δ应收账款) - max(0, -Δ合同负债)
  逻辑：应收账款增加意味着确认了收入但没收现金，需扣除。
        合同负债减少意味着消耗了预收款但计入了收入，也需扣除。

Step 2: 数据提取与分类
  从 DB 提取 inc/bs/cf 三表：revenue, OCF, Capex, D&A, AR, AP, contract_liab,
  asset_disposal, interest_received, other_income, tax_paid, interest_paid,
  intangible_purchase, minority_profit 等

Step 3: V（非经常性）分类
  V1 = 资产处置收益（asset_disposals）
  V5 = 投资收入（interest_received + other_income）
  V_deduct = V2-V4 扣除项（政府补助/保险/其他一次性，默认0——无DB细项数据）

Step 4: W（经营支出，现金口径）
  W = revenue - OCF + interest_paid + tax_paid
  若 W > 95% revenue 或 W < 50% revenue → 回退到 revenue × 0.85（保守默认）

Step 5: Y（资本支出 + 投资）
  Y = Capex(E) + X1(无形资产购买) + X2(隐性支出，默认0)
  Capex(E) = |c_pay_acq_const_fiolta|（购建固定资产、无形资产和其他长期资产支付的现金）
  mcapex_split_pct 来自 Zone J capex_classification.json，默认1.0（全额扣除）

Step 6: 少数股东权益调整
  触发条件：少数股东损益 > 合并净利润 × 10%
  parent_ratio_3y = 归母净利润/合并净利润（近3年均值）
  AA_adjusted = AA × parent_ratio_3y
  逻辑：AA 用合并 OCF 计算（含少数股东现金流），但 GG 分母 MC 是归母市值，
        归母股东无法支配少数股东部分的现金流

Step 7: 年度结余
  annual_surplus = 真实现金收入 + V1 + V5 - V_deduct - W - Y
  AA = max(annual_surplus, 0)  ← 不低于0
  AA₃y = 近3年 AA 均值
```

**AP 驱动伪现金流检测**（Step 7 之后）：
- 计算近5年 AP/Cost 比率（DPO ≈ AP/(Cost/365)）
- 若 DPO 持续拉长且远超行业基准 → 超额AP = 当期AP - Cost×5年前比率
- ap_pct = 年均超额AP / AA₃y × 100
- 若 ap_pct > 20%，Agent 应在 GG 章展示 ap_adjusted_aa 并标注"AA中约X%来自延迟支付供应商"

### 5.4 DDM 模型 & P_base 目标价 (V12.5 更新)

**DDM 估值**（永续增长模型）：
```
公允价 = DPS × (1 + g_base) / (II_adjusted - g_base)
II_adjusted = II_original + 周期调整（强周期+2pct, 弱周期/成长不调整）

阶梯买入价（5级，安全边际递增）：
  1星: DDM公允价 × 1.00  (0% 安全边际)
  2星: DDM公允价 × 0.90  (10% 安全边际)
  3星: DDM公允价 × 0.80  (20% 安全边际)
  4星: DDM公允价 × 0.70  (30% 安全边际)
  5星: DDM公允价 × 0.60  (40% 安全边际)
```

**P_base 目标价** (V12.5 新增, Spec Factor4 Step4)：
```
P_base = MC × (GG / II) / shares
→ 在此价格下，GG 恰好等于 II，即公允价

P_EV = (NetCash + EV × GG_EV / II) / shares（EV双轨触发时）
→ 净现金按面值，经营资产按 GG_EV/II 折现
```

**周期调整** (V12.5 新增)：强周期公司 II +2pct（周期顶部提高门槛，更保守）。

价值陷阱 9 项检测（V12.5 扩展）：净利润趋势、分红可持续性、AP驱动伪现金流、周期顶部风险、负债率、PB、OCF/NP、ROE趋势、大股东行为。

### 5.4b PE 估值对比 (V12.14 新增)

框架输出当前 PE（`factor4.current_pe`），Agent 从 `industry_context.json` 读行业 PE 中位数做对比：

```
当前 PE = MC / NP（归母口径）
行业 PE = industry_context.percentiles.pe_ttm.industry_median
折价 = (1 - 当前PE/行业PE) × 100%
```

用途：揭示市场定价的折价来源。折价 >30% 时，Agent 应分析：
- 归母 vs 合并口径混淆（最常见的估值错误）
- 少数股东结构折价（市场给归母利润打了折扣）
- 低增长预期
- 港股流动性折价

### 5.5 否决门

| 否决条件 | 动作 |
|---------|------|
| R(NP) < Rf (4.0%) | 否决（穿透回报率低于无风险利率） |
| Rf ≤ R(NP) < II × 0.5 | 否决（回报率远低于门槛） |
| II × 0.5 ≤ R(NP) < II | 边界（需额外证据支持） |
| 数据质量 BLOCK | 否决（关键数据不可用） |

### 5.6 决策矩阵（5 状态合成）

| | Turtle: Buy | Turtle: Hold | Turtle: Avoid |
|---|---|---|---|
| **Dayu: Continue** | **Strong Buy** | Cautious Watch | 好公司太贵 — 等待更好价格 |
| **Dayu: Pause** | 价格错配 — 验证定性 | **Hold Review** | Likely Avoid |
| **Dayu: Abandon** | 数据冲突 — 重新核验 | Slow Fade | **Strong Reject** |

**决策优先级规则（强制）**：
1. 定量决定（GG/DDM/否决门）为**第一优先**
2. 定性决定只能调整仓位（Continue→仓位加满，Pause→仓位减半），不能在定量否决时"拉回"决策
3. 禁止"取折中"——如果定量说 Avoid，最终必须是 Avoid 或 Strong Reject，不能变成 Hold

### 5.7 V12 保守偏空原则（判断框架，非死规则）

1. **净现金可及性**：现金在哪→谁有权支配→有无释放先例。若无→标注为期权而非安全边际
2. **竞争性解释校准**：问"最乐观的解释是不是我最想相信的？"→是则下调权重。每种解释必须给**概率百分比 + 验证方法 + 验证时间窗口**
3. **伪现金流识别**：量化不可持续的 OCF 成分→标注可持续 vs 不可持续
4. **审计治理折价**：不能独立验证的关联交易本身就是风险，需定性讨论
5. **单变量依赖三维评估**：恶化空间 × 缓冲厚度 × 验证可观测性。变量涉及永久性毁灭→不论依赖度直接否决

**反模式**：硬编码百分比阈值（如">80%→降仓30%"）。判断不能被数字外包。

### 5.8 事实对账机制（V12 核心创新）

`assemble_report` 的 `_run_quality_checks()` 中包含**程序化事实对账器**：
- 从报告文本中正则提取关键数字（GG、DPO、M来源等）
- 与 `compute_gg`、`compute_aa` 等工具计算结果交叉验证
- 发现矛盾 → 返回 warning → Agent 自己看到 warning 后修正

**原则**：修复 Agent 的认知错误，靠**对账机制**，不靠**prompt 打补丁**。每发现一类新的事实错误，在对账器里加一条正则，而不是在 prompt 里加一条规则。

---

### 5.9 行业对比分析 (V12.17 强化)

`zone_d_industry_context.py` 提供 **12 项指标**的行业百分位排名：

| 指标 | 计算方式 | 用途 |
|------|---------|------|
| 营业收入 | DB 直接读取 | 规模定位 |
| 毛利率 | DB 直接读取 | Ch3 护城河 |
| 营业利润率 | operate_profit/revenue | Ch5 经营效率 |
| 净利率 | n_income_attr_p/revenue | Ch5 盈利质量 |
| ROE | NP/归母权益 | Ch6 财务表现 |
| ROA | NP/总资产 | Ch6 资产效率 |
| 归母净利润 | DB 直接读取 | 规模定位 |
| 总资产 | DB 直接读取 | 规模定位 |
| 资产负债率 | total_liab/total_assets | Ch6 杠杆水平 |
| OCF/NP | n_cashflow_act/n_income_attr_p | Ch6 现金流质量 |
| 总资产周转率 | revenue/total_assets | Ch5 资产效率 |
| 股息率 | DPS/(EPS×15) | Ch7 股东回报 |

核心原则（吸收 Dayu 经验）：**行业对比数据服务于"判断分岔点"**——公司跟行业中位数哪里不同、为什么不同、这意味着什么。毛利率高→Ch3 追问护城河，ROE 高→Ch6 拆杜邦，增速落后→Ch4 问市场份额。

---

## Part 6: Dayu 定性方法论

### 6.1 定性分析 9 章核心关注点

| 章 | 核心问题 | 关键数据源 |
|----|---------|-----------|
| Ch1 公司生意 | 这到底是什么生意？谁付钱？怎么赚钱？在产业链的什么位置？ | read_zone_data(mda+segments), read_section(MDA) |
| Ch2 行业位置 | 行业值得看吗？公司站在什么位置？最关键有利点和硬伤？ | get_peer_comparison, get_global_benchmarks, read_zone_data(segments) |
| Ch3 护城河 | 为什么能持续赚钱？最容易先出问题的是哪一环？现在看比较稳还是偏脆弱？ | read_zone_data(mda), get_peer_comparison, assess_moat |
| Ch4 近期变化 | 过去一年 2-4 个关键变化？把公司带到了什么阶段？为什么是"现在"？ | read_zone_data(mda) 最近年 |
| Ch5 经营表现 | 改善是结构性还是周期性？哪些结果最值得相信？ | read_zone_data(mda+segments), get_financial_trends |
| Ch6 财务表现 | 利润质量、现金创造、资本配置可信度。资本分配是增值/维持还是掩盖问题？ | get_financial_statement(overview), get_financial_trends |
| Ch7 股东回报 | 钱怎么回到股东手里？回报是否由真实现金支撑？有没有被稀释？ | get_financial_statement, read_zone_data(governance) |
| Ch8 治理激励 | 谁在真正做决策？激励是否与长期每股价值绑定？少数股东是否存在双重身份利益冲突？ | read_zone_data(governance), governance_tension.json |
| Ch9 风险否决 | 什么风险最可能推翻"继续研究"前提？否决级风险必须展开触发条件+量化影响+当前状态+监控边界 | read_zone_data(risks+audit) |

### 6.2 证据格式规范

```
✅ 正确格式:
  [source: mda.json FY2025 毛利率=37.1%, 营收=220.7亿]
  [source: 00506_2025_年报.pdf MDA p.13 管理层讨论]
  [source: compute_bundle.json GG_base=8.2%, II=5.5%, AA₃y=156.3M]

❌ 错误格式（禁止输出字段路径）:
  [source: mda.json → mda_key_financials → 2025]
  [source: get_peer_comparison → percentiles → roe]
```

**引用放在每段/每 bullet 末尾**，一段一个合引用。不要逐句打断。连续叙述流畅性优先。

### 6.3 占位符格式（缺口处理）

当某个信息必须保留但暂时无法给出来源时：
```
【占位符】（缺口：{缺失的具体信息} ｜ 需要：{需要什么类型的来源} ｜
 已检索范围：{已检索过的文档} ｜ 下一步：{建议的补强路径}）
```

### 6.4 定性→定量桥接

完成 Part A 全部 9 章并审计通过后，Agent 应：
1. 读取所有定性章节，提取 `qualitative_summary.json`，包含 7 个关键字段：
   - `moat_rating`（护城河评级：Wide/Narrow/None）
   - `moat_sources`（护城河来源列表）
   - `b_penalty_evidence`（B类惩罚证据描述）
   - `g_base_context`（增长基准上下文，来自Ch3/Ch5定性判断）
   - `earnings_quality`（盈利质量评级+注释）
   - `non_recurring_items`（识别到的非经常项目列表）
   - `data_discount_signals`（数据折扣信号列表）
   - `veto_level_risks`（否决级风险列表）
2. 这些字段用于增强 Zone J 参数估计（moat/capex/earnings_quality/data_quality）

### 6.5 GG 精算 12 步完整推导（Ch11 强制要求）

Ch11 GG 章必须展示完整推导（对标海螺水泥报告 2864 行深度），不能只输出一个最终数字：

```
(1) 参数表 — 列出 NP_avg/OE_avg/AA_avg/M/Q/MC/g_adj/II 全部8个参数，标注来源
(2) 方法论检查 — OCF/NP背离>2x？折旧/NP>50%触发重资产豁免？
(3) AA 逐年表 — 调 compute_aa 展示 9年FCF+收款比率+趋势判断
(4) GG 公式完全展开 — 逐行写 GG_np/G_oe，每步代入数字
(5) 三档情景 — 悲观(NP-15%)/基准/乐观(NP+15%)，标注每档假设差异
(6) M 值溯源 — 标注 M 来源(computed/fallback)+样本数，若 fallback 必须警示
(7) HH 偏离 — |R(NP)-GG|，>3pct→因子2不适用
(8) 敏感性 — "若股价翻倍，GG降至X%""若M降至0.4，GG降至X%"
(9) 反向压力测试 — 列出至少2个能让GG<II的极端情景及所需条件
(10) AP/DPO 检测 — 引用 compute_aa 的 ap_driven_analysis 结果
(11) 少数股东调整 — 引用 compute_bundle 的 minority_adjustment
(12) 隐含PE对比 — GG隐含PE vs DDM隐含PE，分析估值逻辑前提差异
(13) 治理折价与少数股东调整 (V12.15新增) — 当 minority_adjustment 存在或 governance_tension_rating != "low" 时强制执行：
     (a) 引用 Ch8 少数股东治理张力分析的结论
     (b) 引用 governance_tension.json 的 governance_discount，解释治理折价如何叠加到 data_discount
     (c) 讨论 FCFE GG 的归母比例调整是否完全捕捉了治理现实
     (d) 讨论治理结构改善的可能性及对 GG 的潜在影响
```

### 6.6 关键输入成本敏感性（通用规则）

在 Ch11 GG 和 Ch12 DDM 中，检查公司是否存在**由外部方定价的关键输入品**：
- 特许经营/品牌授权 → 浓缩液/特许权使用费由品牌方定价
- 大宗商品依赖 → 原材料价格由市场决定
- 单一供应商集中 → 关键零部件定价权在供应商手中
- 监管定价 → 产品价格受政府管制

若发现上述模式，**必须对关键输入品提价 5%/10%/15% 做敏感性分析**，量化对毛利率和 GG 的冲击。每条情景附带**概率估计**（高/中/低 + 百分比区间 + 判断依据）。

---

## Part 7: 质量保证体系

### 7.1 审计规则（来自 Dayu audit_rules.py）

| 规则 | 名称 | 检查内容 | 严重度 | 处理 |
|------|------|---------|--------|------|
| P1 | 结构匹配 | 章节结构与骨架标题顺序不一致 | error | REGENERATE |
| P2 | 内容长度 | 定性章<80行，定量章<120行 | error | REGENERATE |
| P3 | 证据小节 | 缺少"### 证据与出处" | error | REGENERATE |
| S1 | 占位符 | `[?]` `[missing]` `[待填充]` `【占位符】` | error | PATCH/REGENERATE |
| E1 | 证据密度 | 数字断言>20且 source 锚点<数字/10 | warn | PATCH |
| C2 | 禁止内容 | 命中 must_not_cover 关键词 | error | PATCH/REGENERATE |
| S2 | 数值一致 | 全文 GG/II/Rf 值不一致 | warn | PATCH |

**结构违规 (P1/P2/P3) → REGENERATE**。
**>3个 error → REGENERATE，≤3个 error → PATCH**。
**仅 warn → PATCH**。
**无违规 → PASS**。

### 7.2 审计循环

```
write_chapter → 自动审计（返回 audit 字段）
  ├─ passed=true → 进入下一章
  └─ passed=false → 重写本章 → audit_chapter
       ├─ passed=true → 进入下一章
       └─ passed=false → 再重写（最多2次）→ 即使warn也继续下一章
```

**规则**：写完一章立即审计，不允许攒到全部写完再批量审计——那会导致"发现了违规但不修"。

### 7.3 质量门禁（assemble_report 时触发，7 层检查）

1. **基础质量门禁**（`quality_gate.check`）：占位符/表格数/关键参数/变量残留
2. **证据锚点验证**（`evidence_citation.validate_evidence_coverage`）：覆盖率≥30%
3. **Zone B 使用率检查**：可用 Zone B 文件中被引用比例≥50%，否则 warning
4. **增强质量门禁**（`enhanced_quality_gate.enhanced_check`）：结论一致性 + 风险披露 + Token 效率
5. **数据缺口扫描**（`data_gap_scanner.scan_report`）：统计 `⚠️` 标记
6. **内容审计**：
   - M fallback 检查（Ch11/12 中若 M=fallback 但未展示校正值 → warning）
   - 关联交易量化（Ch8/9 中提到关联交易但缺具体金额 → warning）
   - GG/DDM 前提一致性（Ch13 中提到"一致"但未分析估值逻辑前提差异 → warning）
7. **事实对账器**（V12 核心）：GG 数字/AP-DPO 判断/M 来源 → 与工具结果交叉验证

### 7.4 报告最低标准

- **最低**：800 行（低于此质量门禁不通过）
- **警告**：< 2000 行
- **建议**：≥ 3000 行（对标海螺水泥 2864 行）

### 7.5 报告信息密度（V12.16 新增）

**问题**：Agent 逐章独立写作，天然倾向重复——同一论点（如"净现金/市值47.1%"）在 Ch3/Ch6/Ch11/Ch12 反复展开。

**机制 1 — 写作密度规则**（system prompt 内置）：
- 同一论点只在首次出现时详细展开，后续章用 `(见 ChX)` 引用
- 每个 `[source: X]` 全报告最多出现 3 次
- 禁词列表："接下来我们将分析..."、"综上所述..."、"值得注意的是..." — 全删
- 每个 bullet 必须有增量信息

**机制 2 — 全局去重压缩**（`agent_loop._compress_report()`）：
- `assemble_report` 后自动运行，一次 LLM 调用
- 去重跨章重复段落，目标缩减 20-30%
- 数字/表格/`[source: X]` 原样保留
- 压缩后 < 原 30% → 保留原版（防止误删）

**效果**：报告长度控制，信息密度提升，不牺牲分析深度。

---

## Part 8: 运行手册

### 8.1 环境变量

```bash
# .env 文件（位于框架根目录）
TUSHARE_TOKEN=your_token_here        # Tushare Pro API token（必需，用于市场数据）
ANTHROPIC_API_KEY=sk-ant-...          # Anthropic API key（全自动模式）
DEEPSEEK_API_KEY=sk-...               # DeepSeek API key（备选，走 OpenAI 兼容 API）
PORTFOLIO_CAP_PCT=5                   # 组合仓位上限 %
TUSHARE_API_URL=                      # 自定义 Tushare 代理（留空用官方）
VIP_MODE=true                         # VIP 端点自动升级（第三方代理需设 false）
```

**LLM Provider 自动检测**：
- `ANTHROPIC_API_KEY` 以 `sk-ant-` 开头 → Anthropic Messages API
- `DEEPSEEK_API_KEY` 设置 → DeepSeek OpenAI 兼容 API（httpx 直调，零 SDK 依赖）
- 都不设 → 生成 `_v12_system_prompt.md` + `_v12_tools.json`，需手动处理

### 8.1b 多 Key 池（V12.17 新增）

`analyze.sh` 支持多 API Key 自动分配，并行跑不同股票时不冲突：

```bash
# 设置 3 个 Key（analyze.sh 内置默认值，也可环境变量覆盖）
export DEEPSEEK_API_KEY_1=sk-xxx
export DEEPSEEK_API_KEY_2=sk-yyy
export DEEPSEEK_API_KEY_3=sk-zzz

# 按股票代码 hash 自动选 Key，并行不冲突
./analyze.sh 00506 &
./analyze.sh 01502 &
./analyze.sh 000651 &
```

### 8.1c 报告归档 (V12.18 新增)

每次重分析时，旧报告和旧 `compute_bundle.json` 自动归档到 `output/{code}_*/history/` 目录，文件名带时间戳。仪表盘 `analysis_history` 表同步保留每次分析记录。不会丢历史数据。

### 8.1d web_search 内置工具 (V12.18 启用)

Claude 内置 `web_search` 和 `web_fetch` 已启用。Agent 写 Ch2 国际对标时会自动搜索国际同行财务数据（无需手动维护 `global_benchmarks.json`）。搜索结果由 Claude 服务端执行，框架不用管。

### 8.2 完整运行命令

```bash
cd Turtle_investment_framework

# 一键分析（推荐）
./analyze.sh 01502

# 完整流程（从零开始）
python -m turtle_agent.run --code 01502 --unified

# 仪表盘生成
python scripts/portfolio_dashboard.py

# 仪表盘（含 invest 同步 + 实时行情）
python scripts/portfolio_dashboard.py --sync-invest

# 导出 invest 可导入的 JSON
python scripts/portfolio_dashboard.py --export-only

# 干跑验证
python -m turtle_agent.run --code 01502 --unified --dry-run
```

### 8.3 股票代码格式

- A股：`600519.SH`（上海）、`000858.SZ`（深圳）
- 港股：`00700.HK`、`06668.HK`
- 美股：`AAPL`（通过 SEC EDGAR）
- 自动推断：`01502` → `01502.HK`，`600519` → `600519.SH`，`000858` → `000858.SZ`

### 8.4 输出文件清单

每个股票分析完成后，`output/{code}_*/` 目录下会生成：

```
analysis_contract.json          # Phase 0: 分析合约
compute_bundle.json             # Phase 1: 定量计算核心输出
gg_override.json               # Phase 1.3: PDF附注提取的GG结构化覆盖（可选）
financial_trends.json           # Phase 1.5: 财务趋势
industry_context.json           # Phase 1.5: 行业对比
{year}_年报.pdf                 # Phase 0.5: 年报PDF（多份）
{year}_年报.md                  # Phase 2.1: 年报全量Markdown
page_map_{year}.json            # Phase 2: 章节页码导航
pdf_sections_{year}.json        # Phase 2.1: 结构化文本
zone_b_{year}_partial.json      # Phase 2.3: 年度LLM提取中间产物
mda.json                        # Phase 2.4: Zone B 管理层讨论
segments.json                   # Phase 2.4: Zone B 分部报告
risks.json                      # Phase 2.4: Zone B 风险因素
governance.json                 # Phase 2.4: Zone B 公司治理
audit.json                      # Phase 2.4: Zone B 审计意见
moat_assessment.json            # Phase 3: Zone J 护城河评估
capex_classification.json       # Phase 3: Zone J Capex分类
earnings_quality.json           # Phase 3: Zone J 盈利质量
data_discount.json              # Phase 3: Zone J 数据折价
governance_tension.json          # Phase 3: Zone J 治理张力（V12.15新增）
qualitative_summary.json        # Agent Loop: 定性摘要（桥接定量）
_ch00.md ... _ch13.md           # Agent Loop: 各章文件
{code}_分析报告_v12.md           # 最终报告
_tracker.json                   # 执行追踪
_v12_system_prompt.md           # (无API key时) 生成的prompt
_v12_tools.json                 # (无API key时) 工具schema
```

### 8.5 常见问题

**Q: yfinance 股本数据错误导致 GG 虚高？**
A: `compute_gg` 和 `get_market_data` 已内置自动检测和修正。Agent 应在写 GG 章前调用 `get_market_data` 检查 `shares_warning` 字段。若 `shares_m_corrected` 与 `shares_m` 差异 > 5%，GG 会自动重算。

**Q: Zone B 数据全空怎么办？**
A: `agent_loop.py` 的 `_load_context()` 会检测薄数据并标记 `_thin: True`。Agent 收到数据可用性报告后，应改用 `read_section` 直接读 PDF 原文。

**Q: M 值是 fallback 怎么办？**
A: `compute_gg` 会自动从 DPS/EPS 尝试计算真实 M 值。Agent 在报告中应展示自动计算的 M 值并标注来源。若确实无分红数据，须在报告中警示"M 值使用行业默认 0.7，实际支付率待验证"。

**Q: GG 不可用（净现金/MC 过高）怎么决策？**
A: `evaluate_decision` 返回 Hold (low confidence)，rationale 中说明原因。Agent 在 Ch13 综合决策中需手动评估 DDM + PB + 股息率，并触发**资产陷阱三段论**：
1. 现金在谁手里（控股股东/公司账上/中小股东可及？）
2. 催化剂在哪里（有无特别分红/大额回购/资产剥离计划？）
3. 历史验证（过去5年有无释放股东价值的先例？）

**Q: 如何续跑中断的分析？**
A: 使用 `--skip-prepare` 跳过 Phase 0-3.5，直接进入 Agent Loop。Agent 会自动检测已有 `_ch*.md` 文件并跳过审计已通过的章节。

---

### 5.10b 决策矩阵更新 (V12.18)

在原 5 状态矩阵基础上新增两条覆盖规则：

| 场景 | 触发条件 | 动作 |
|------|---------|------|
| 逆向覆盖 | 定量 Avoid 仅因 S2 扰动豁免 + PE<12x | Avoid→Cautious Watch（1-2%） |
| 定性降级 | 定量 Strong Buy + 定性 Pause | Strong Buy→Buy（仓位降至1-2%） |

核心理念：定量看价格，定性看风险。价格便宜但风险未释放时，买但不重仓。

### 5.10c 框架适用边界 (V12.18 新增)

Turtle 模型的底层假设（OCF代表经营现金流、Capex可预测、DDM适用）对以下公司类型**本质上不完全成立**。`compute_bundle.py` 会自动检测并写入 `factor2.framework_limitations`，Agent 必须在 Ch0 和 Ch13 醒目展示。

| 类型 | 检测条件 | 影响 | 建议 |
|------|---------|------|------|
| 控股/投资平台 | invest_income > NP×0.5 | S2/GG基于OCF的假设部分失效 | FCF已用投资收入重算，AA仅供参考 |
| 轻资产服务/物业 | OCF/Rev<10% | AA保守路径严重低估自由现金流 | 以FCFE GG为主要参考 |
| 零分红/极低分红 | DPS<0.01 | DDM完全失效 | 以P_base和FCFE GG为估值参考 |
| OCF极端波动 | OCF_CV>1.0 | 当前GG可能是周期位置而非可持续水平 | 结合Ch4/Ch9判断周期位置 |

---

## Part 9: V12 关键设计决策

### 9.1 为什么是单 Agent + 工具循环

**V10 架构**：多 Agent 并行写作管线（ThreadPoolExecutor 并行写章 → 逐章审计 → 修复循环 → 决策合成 → 组装）。

**V12 架构**：单 Agent + 工具循环（借鉴 Dayu "LLM in the loop"）。

**优势**：
- Agent 在统一上下文中逐步分析，保持全局一致性（V10 并行章之间可能矛盾）
- 按需调用工具获取数据，不预先推送全量数据（避免上下文污染）
- 写 → 审 → 修在统一消息流中完成，决策连贯
- 定性（Dayu）和定量（Turtle）在同一个 Agent Loop 内完成，避免桥接信息丢失
- 单 Agent 可以引用前文章节的结论，V10 并行模式下各章彼此不可见

### 9.2 Agent Prompt 瘦身原则

**规则分层**：
- **Agent system prompt**（`agent_loop.py:_build_system_prompt`）：只放**通用方法论**——决策优先级、证据格式、价值陷阱方向、竞争性解释概率。这些规则适用于所有公司。
- **模板 ITEM_RULE**（`report_template_v12.md`）：放**公司特异规则**——每条带 `facets_any` 条件，只在公司匹配时才触发。

**判断标准**：新增规则时，问自己——"这条规则对茅台和万科都适用吗？"
- 是 → 放 agent prompt
- 否 → 放模板 ITEM_RULE，加 `facets_any`

**反模式**：不要在 agent prompt 里堆砌"若XX则YY"的条件判断。那是模板 ITEM_RULE 的职责。

### 9.3 事实对账原则

Agent 的叙事不可信，工具的计算才可信。不在 prompt 里教 Agent "不要写错"——而是在 `assemble_report` 的 `_run_quality_checks` 里加**程序化事实对账器**：
- 从报告文本中正则提取关键数字（GG、DPO、M来源等）
- 与 `compute_gg`、`compute_aa` 工具计算结果交叉验证
- 发现矛盾 → 返回 warning → Agent 自己看到 warning 后修正

每发现一类新的事实错误，在对账器里加一条正则，而不是在 prompt 里加一条规则。

### 9.4 框架保守偏空

框架默认保守偏空——对乐观解释要求更高的证据标准，对悲观情景赋予更重的权重。这不是死规则，而是**判断框架**——Agent 需展示推理过程，而非机械套用。

**核心判断维度**：
1. 净现金可及性——便宜能否被实现
2. 竞争性解释——最乐观的解释是不是我最想相信的
3. 伪现金流——OCF 中有多少不可持续
4. 审计治理——关联交易是否可独立验证
5. 单变量依赖——恶化空间 × 缓冲厚度 × 验证可观测性

### 9.5 V12.15 国际化对标 + 治理张力 (2026-07-17)

**国际化对标背景**：`zone_d_industry_context.py` 只能从 DB (A股+港股) 找同行，无法覆盖 CCEP、太古可口可乐等国际可比公司。Agent 写 Ch2 时缺少全球参照系，无法判断中国公司的结构性折价/溢价来源。

**治理张力背景**：`compute_bundle.py` 的 AA Step 6 和 FCFE GG 已对 parent_ratio 做定量调整，但框架缺少对少数股东双重身份（如供应商+股东）利益冲突的结构化分析。Agent 在报告中机械引用 parent_ratio 但不追溯治理根源。

**设计方案**：
- **国际化对标**：新增 `config/global_benchmarks.json`（手动维护的国际对标公司数据库）+ `get_global_benchmarks` 工具。按商业模式关键词匹配，首期覆盖装瓶商。数据标注 `confidence` 和 `source_year`，Agent 引用时需注明数据来源。
- **治理张力**：新增 Zone J 第 5 个 Agent `governance_tension`，从 `governance.json` 提取少数股东结构、双重身份、利益冲突，评估治理折价（0-10%）。`compute_bundle.py` 将治理折价叠加到 `data_discount` 上形成 `total_discount`。Ch8 模板新增"少数股东结构与治理张力"ITEM_RULE（回答三个核心问题），Ch11 新增步骤(13)治理折价推导。
- **事实对账器增强**：若 `minority_adjustment` 存在但 Ch8 未讨论治理张力 → warning；若 `governance_tension.json` 存在但 Ch11 未引用 → warning。

---

## 附录: 关键常量速查

| 常量 | 值 | 说明 | 所在文件 |
|------|-----|------|---------|
| II 默认 | 5.5% | 门槛回报率 | thresholds 表可逐股覆盖 |
| Rf | 4.0% | 无风险利率 | compute_bundle.py |
| Q | 0.10 | 股息税率 | compute_bundle.py |
| FX | 0.9346 | HKD→RMB | compute_bundle.py |
| g_base 默认 | 2.0% | 永续增长率基准 | Zone J 可覆盖 |
| b_penalty 默认 | 0.25 | B类业务惩罚 | Zone J 可覆盖 |
| M fallback | 0.7 | 分红率行业默认（港股） | compute_bundle.py |
| mcapex_split_pct 默认 | 1.0 | 维持性Capex占比（全额扣除） | Zone J capex 可覆盖 |
| data_discount 默认 | 15% | Zone J 数据不完整折价 | Zone J data_discount 可覆盖 |
| governance_discount 上限 | 10% | 治理张力折价上限（V12.15新增） | Zone J governance_tension 可覆盖 |
| total_discount 上限 | 50% | 数据+治理总折价上限 | compute_bundle.py |
| max_iterations | 30 | Agent 最大循环迭代次数 | agent_loop.py |
| max_tokens_per_call | 32768 | 单次 LLM 调用最大输出 token | agent_loop.py |
| temperature | 0.3 | Agent 采样温度 | agent_loop.py |
| 审计最大重试 | 2次 | 同一章最多重写次数 | agent_loop.py system prompt |
| 金额单位 | 百万元 RMB | 全局统一 | 所有 Python 脚本 |
| 报告最低行数 | 800行 | 低于此质量门禁不通过 | write_tools.py |
| 报告建议行数 | ≥3000行 | 对标海螺水泥 2864 行 | write_tools.py |
| 否决: R < Rf | 否决 | 穿透回报率低于无风险利率 | compute_bundle.py |
| 否决: R < II×0.5 | 否决 | 回报率远低于门槛 | compute_bundle.py |
| 少数股东调整阈值 | 10% | 少数股东>NP 10%触发调整 | compute_bundle.py |
| 资产跳升阈值 | 50% YoY | 触发断点检测 | pre_analysis_phase.py |
| 商誉跳升阈值 | 20% 总资产 | 触发断点检测 | pre_analysis_phase.py |
| 收入脱钩阈值 | 30% | 资产跳升但收入增长<30%=断点 | pre_analysis_phase.py |
| 成长股强制窗口 | 5年 | revenue_3y_CAGR > 15% | pre_analysis_phase.py |
