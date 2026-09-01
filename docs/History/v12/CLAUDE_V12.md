# CLAUDE.md — 龟龟投资策略框架 V12.19

> **ARCHIVED / V12：**旧Claude执行说明，不得被加载为当前仓库指令。当前兼容入口位于仓库根 `CLAUDE.md`，并统一服从 `AGENTS.md`。

> **📖 文档**: `docs/V12_MANUAL.md`（引擎手册）| `docs/DB_SPEC.md`（DB规范）| `docs/ANALYSIS_HORIZON.md`（时域设计）
> V12.19: 卫星上市标的机制（B股/ADR/多地上市）+ data_source_code + 货币感知定价 + 自动链接母标文件
> V12.18: 保守偏空校正(S2扰动豁免+g_adj floor+逆向覆盖+定性降级+已定价风险) + 控股豁免 + 框架局限性检测 + CSMAR全量修复 + web_search启用 + 报告归档。
> 一个命令跑完全流程 `python -m turtle_agent.run --code X --unified`。
> Python 负责标准化加工，LLM 负责需要判断的转化。

## 架构（6 Phase）

```
Phase 0: 前置诊断（pre_analysis_phase — 断点检测 + 双维度周期分类 + 分析窗口）
Phase 0.5: 年报自动补全（download_report.py — cninfo + cre8ir）
Phase 1: Zone A Python 定量（compute_bundle --contract + --zone-j / financial_trends / industry_context）
Phase 2: 数据打包 + 定性提取（DB 定量 + PDF 定性分工）
  2.1: pdf_preprocessor.py → pdf_sections_{year}.json (PDF 章节文本, 纯 Python)
  2.2: build_full_text.py → pdf_full_text.json (多年度全文组装, 嵌入 DB 财务快照)
  2.3: zone_b_v8.py --stage year → zone_b_{year}_partial.json (LLM 年度提取, 并行)
  2.4: zone_b_v8.py --stage master → mda/segments/risks/governance/audit.json (LLM 汇总)
  2.5: pdf_page_locator.py → page_map_{year}.json (页面导航)
  2.2: pdf_page_locator.py → page_map + 章节导出
  2.3: 协调器按 page_map Read PDF → 提取定性 → Zone B JSON
Phase 3: Zone J 判断型参数化层（moat/capex/earnings_quality/data_discount，每个参数附带 evidence_ref）
Phase 4: Zone C V10 写管线（分章节并行写作 → 审计修复 → 决策综合 → 来源清单 → 组装）
Phase 5: 验证（citation_verifier / boundary_validator / quality_gate / enhanced_quality_gate）
```

## Zone C V10 写管线（Phase 4 新架构）

```
模板解析（template_parser.py）
  → 构建 ChapterTask 列表
  → 并行写中间章节（Chapter 1/3/4/5/6/7, ThreadPoolExecutor）
  → 逐章审计（audit_rules.py: E1-E2/C1-C2/S1-S2, 可编程 + LLM 双轨）
  → 自动修复/重写（repair_executor.py: patch/regenerate）
  → 写决策章（decision_synthesizer.py: Continue/Hold/Abandon）
  → 写 Executive Summary
  → 构建来源清单（source_list_builder.py）
  → 组装最终报告（build_report_markdown）
```

## V12.19 卫星上市标的机制

同一公司在多地上市（A股+B股 / AH股 / ADR），财务数据完全相同，仅价格不同。
框架通过 `stocks.data_source_code` 字段支持"卫星上市标的"模式：

### 使用方式
```bash
# 1. 在 stocks 表中添加卫星标的，data_source_code 指向母标
#    INSERT INTO stocks (ts_code, data_source_code, currency, ...) VALUES ('900936.SH', '600295.SH', 'USD', ...)

# 2. 像普通股票一样跑分析
python -m turtle_agent.run --code 900936.SH --unified
```

### 自动行为
- **`compute_bundle_db`**：自动检测 `data_source_code` → 链接母标的 zone_j/pdf/contract 文件 → 用卫星标的价格独立计算
- **`load_from_db`**：财务数据自动回退到母标的 `annual_financials`
- **`compute_from_db`**：货币感知 — USD 用 fx=7.15，HKD 用 fx=0.9346
- **`compute_bundle.json`**：自动生成 `trading_info` 字段，Agent 读报告时知晓数据来源

### Agent 感知
Agent 通过两个渠道知道这是卫星标的：
1. `compute_bundle_db` 返回值中的 `trading_note` 字段
2. `compute_bundle.json` 中的 `trading_info` section

### 仪表盘
卫星标的独立显示在 portfolio.db 中，有自己的 GG / P_base / DDM / 决策。

### 示例
| 母标 | 卫星标的 | 关系 |
|------|---------|------|
| 600295.SH 鄂尔多斯 (A股 RMB) | 900936.SH 鄂尔多斯B (B股 USD) | A+B股 |
| 600585.SH 海螺水泥 (A股) | 00914.HK 海螺水泥 (H股) | AH股 |
| 00700.HK 腾讯 (H股) | TCEHY (ADR USD) | HK+ADR |

## 核心约束

1. **Python 负责会计数据的标准化提取和统计加工；LLM 负责需要商业判断的参数估算和叙事构建。**
0. **数据来源分工（架构原则）**：定量数据一律走 `stock_analysis.db`（annual_financials 表），PDF 只提供定性叙事（管理层讨论、风险描述、治理结构、审计意见、分部经营分析）。`compute_bundle.py` / GG / DDM 的数据源是 DB，不依赖 PDF 提取的数字。`build_full_text.py` 和 `zone_b_v8.py` 在构建提取 prompt 时自动嵌入 DB 财务数据作为定量上下文，LLM 专注定性洞察提取。
2. 边界不在"数字/文字"，而在"不需要判断的加工"和"需要判断的转化"之间。
3. Zone J 每个参数必须附带 `evidence_ref`（指向 Zone B JSON 的具体字段）。
4. 金额单位：百万元 RMB。缺失字段写 `⚠️ 数据不可用`，禁止编造。
5. V10 新增：每个数据断言必须附带 `[source: 文件名]` 证据锚点。
6. V10 新增：每章审计通过（无 E1/S1/S2 error）后方可进入组装。

## 写作铁律（不可简化版，Agent 每次写报告必须遵守）

以下规则已写入 agent_loop.py system prompt，在此备份防止误删。

### 来源引用（V12.18 自动化）
- 数据断言后加 `[source: 文件 数据]` 即可，格式随意
- 组装报告时自动提取为文末 `[^N]` 脚注 + `_sources.json`
- web_search 来源保留内联，其他全部脚注化

### Ch11 GG 章 12 步推导（禁止只输出一个数字）
(1) 参数表 (2) 方法论检查 (3) **AA 逐年表**（调 compute_aa 展示各年 FCF+收款比率+趋势判断） (4) GG 公式展开 (5) 三档情景 (6) M 值溯源 (7) HH 偏离 (8) 敏感性 (9) 反向压力测试 (10) AP/DPO 检测 (11) 少数股东调整 (12) λ 推导 (13) 治理折价与少数股东调整。对标海螺水泥 2864 行报告深度。

### 章节结构
- 章节大标题必须用 `## `（h2），HTML TOC 侧栏只抓 h2
- 每章三部分：`### 结论要点` / `### 详细情况` / `### 证据与出处`
- `#### ` 四级标题分隔子节

### 货币单位
- 港股以 HKD 为主，A 股以 RMB 为主。双币种格式：`X.XX HKD (≈ Y.YY RMB)`
- P_base/DDM 公允价/买入价优先用交易货币

### 其他
- 每章 ≥1 张同行对比表（≥4 家 × ≥5 指标）
- 特别股息必须拆分标注"常规 DPS=X，特别 DPS=Y（一次性）"
- 框架局限性警告必须在 Ch0 和 Ch13 醒目展示
- 每写完一章立即 audit_chapter

## 关键文件

- **V11 统一入口**: `python -m turtle_agent.run --code X` 或 `python scripts/write_pipeline.py --code X`
- **V10 回退**: `python scripts/write_pipeline.py --code X --legacy-v10`
- **Agent 框架**: `scripts/turtle_agent/` (llm_client / tool_registry / agent_loop / scene_preparer / run)
- **工具集**: `scripts/turtle_agent/tools/` (read / calc / write / phase — 19 tools auto-discovered)
- 协调器: `coordinator_v11.md`（V11 单 Agent prompt）| `strategies/turtle/coordinator_v10.md`（V10 遗留）
- 前置诊断: `scripts/pre_analysis_phase.py`（断点+CV+三轨+N年窗口）
- PDF 导航: `scripts/pdf_page_locator.py`（TOC解析+附注扫描+章节导出）
- Zone A: `scripts/compute_bundle.py`（支持 --contract 动态窗口 + --zone-j 精炼参数）
- Zone A 辅助: `scripts/build_financial_trends.py`, `scripts/zone_d_industry_context.py`
- Zone B: `scripts/pdf_page_locator.py` + 协调器 Read / `scripts/zone_b_v8.py`（fallback）
- Zone J: `scripts/zone_j_agent.py`（支持 --validate 参数审计，V12.15: 5 Agent并行含 governance_tension）
- **V12.17 新增/强化**:
  - 行业对比: `zone_d_industry_context.py` 指标 6→12，`get_peer_comparison` 返回完整同业数据
  - 国际对标: `get_global_benchmarks` 自动生成 web_search 查询（不再依赖 static JSON）
  - 仪表盘: `portfolio_dashboard.py` (DB-backed) + `portfolio_db.py` + 实时行情 + 组合GG
  - 批量分析: `analyze.sh` 支持多 Key 池自动分配
  - 事实对账器: GG/DPO/分红 三项规则
  - 下载验证: `download_annual_reports` 实际检查文件存在性
- **Zone C V10 写管线**:
  - 模板: `templates/report_template_v10.md`（9 章 + HTML 注释合约）
  - 模板解析: `scripts/template_parser.py`, `scripts/template_validator.py`
  - 管线编排: `scripts/write_pipeline.py`（WritePipelineRunner）
  - 章节写作: `scripts/chapter_writer.py`
  - 领域模型: `scripts/models.py`
  - 审计: `scripts/chapter_audit.py`, `scripts/audit_rules.py`
  - 修复: `scripts/repair_executor.py`
  - 证据: `scripts/evidence_citation.py`, `scripts/source_list_builder.py`
  - 决策: `scripts/decision_synthesizer.py`
  - 渲染: `scripts/render_report.py`
  - 追踪: `scripts/execution_tracker.py`
  - 场景配置: `config/scenes.yaml`, `scripts/scene_config.py`
  - 入口: `scripts/zone_c_chain.py --pipeline`（委托给 write_pipeline.py）
- 验证: `scripts/boundary_validator.py`, `scripts/citation_verifier.py`（支持 --evidence-only）, `scripts/quality_gate.py`, `scripts/enhanced_quality_gate.py`
- 数据库: `stock_analysis.db`（8,433 只股票，2005-2025）
- 文档: `docs/V12_MANUAL.md`（使用手册）, `docs/ANALYSIS_HORIZON.md`（时域设计）, `docs/DB_SPEC.md`（数据库规范）

## Dayu 集成模块（V10 新增）

从 Dayu Agent 项目提取的 11 个模块，零新增 pip 依赖：

### 下载器（`scripts/downloaders/`）— 三市场财报下载
- `cninfo.py` — A股巨潮：分类API + 修订版优先 + 财年正则推断 + 港股fulltext回退
- `hkexnews.py` — 港股披露易：titleSearchServlet API + stockId解析 + 英文过滤
- `sec.py` — 美股SEC EDGAR：ticker→CIK + submissions + index.json主文档解析 + 限流

### 算法组件（`scripts/` 顶层）
- `financial_classifier.py` — 财务报表分类器：60+中英双语关键词，四组证据集（利润表≥3/资产负债表≥4/现金流量表≥2），零依赖
- `sec_items.py` — SEC Item语义映射：10-K/10-Q/20-F 全Item→SectionType，Part消歧，路径构建
- `financial_synonyms.py` — 财务同义词：30+组中英双语同义词，5类意图分类，噪声上下文过滤
- `bm25f_scorer.py` — BM25F段落检索排序：6字段加权（title 3x/item 2x/content 1x），stdlib only
- `sec_html_rules.py` — EDGAR HTML预处理：SGML剥离、封面检测、标题横线识别

### 解析器（`scripts/parsers/`）
- `num_parser.py` — 数字解析：括号负数、货币剥离（HK$/USD/RMB等）、欧式分隔符规范化
- `date_parser.py` — 日期/期间解析：14种格式+财期推断+多语月份映射（英/西/葡/法）

### CLI 入口
- `download_report.py` — `--auto`(A股) / `--hk`(港股) / `--market US`(美股) / `--url`(直链)

### 搜索与存储（V10 新增）
- `adaptive_search.py` — 自适应搜索管线：查询诊断(歧义度+意图)→ 三层扩展(短语/同义词/token)→ 意图过滤→ 排序
- `repository_protocols.py` — 仓储窄协议：6个Protocol(Batching/CompanyMeta/SourceDocument/ProcessedDocument/DocumentBlob/FilingMaintenance)，作为 stock_analysis.db 重构设计模板

## V10 vs V9 关键变化

| 维度 | V9.3 | V10 |
|------|------|-----|
| Zone C 模式 | 单体 C_FULL Agent | 分章节并行写作管线 |
| 模板 | 硬编码 ~400 行 [/?] 占位符 | 正式模板 + HTML 注释合约 |
| 质量保证 | 事后 quality_gate | 逐章审计 + 自动修复循环 |
| 证据引用 | 无强制 | 每项数据断言需 [source: X] |
| 决策 | 散落在因子4中 | 独立决策章（Continue/Hold/Abandon） |
| 报告格式 | Markdown + 基础 HTML | Markdown + HTML + PDF + DOCX |
| 并行 | 无 | ThreadPoolExecutor 多章并行 |

## V12 框架保守主义原则（2026-07-14 确立）

框架默认**保守偏空**。以下不是死规则，而是**判断框架**——Agent 需展示推理过程，而非机械套用。

1. **净现金可及性**：现金在哪→谁有权支配→有无释放先例。若无→标注为期权而非安全边际
2. **竞争性解释校准**：问"最乐观的解释是不是我最想相信的？"→是则下调权重
3. **伪现金流识别**：量化不可持续的 OCF 成分→标注可持续 vs 不可持续
4. **审计治理折价**：不能独立验证的关联交易本身就是风险，需定性讨论
5. **单变量依赖三维评估**：恶化空间×缓冲厚度×验证可观测性。变量涉及永久性毁灭→不论依赖度直接否决

**反模式**：硬编码百分比阈值（如">80%→降仓30%"）。判断不能被数字外包。

## V12 事实对账原则（2026-07-14 确立）

**Agent 的叙事不可信，工具的计算才可信。** 不在 prompt 里教 Agent "不要写错"——而是在 `assemble_report` 的 `_run_quality_checks` 里加**程序化事实对账器**：

1. 从报告文本中正则提取关键数字（GG、DPO、M来源等）
2. 与工具计算结果（compute_gg、compute_aa、compute_ddm）交叉验证
3. 发现矛盾 → 返回 warning → Agent 自己看到 warning 后修正

**原则**：修复 Agent 的认知错误，靠**对账机制**，不靠**prompt 打补丁**。每发现一类新的事实错误，在对账器里加一条正则，而不是在 prompt 里加一条规则。

## V12 Agent Prompt 瘦身原则（2026-07-13 确立）

**规则分层**：
- **Agent system prompt (`agent_loop.py:_build_system_prompt`)** → 只放**通用方法论**：决策优先级、证据格式、价值陷阱方向、竞争性解释概率。这些规则适用于所有公司。
- **模板 ITEM_RULE (`report_template_v12.md`)** → 放**公司特异规则**：每条带 `facets_any` 条件，只在公司匹配时才触发。例如：
  - 资产陷阱三段论 → `facets_any: [高资本开支, 周期性强, 上游资源/勘探开发, REIT/基础设施, 银行, 保险]`
  - GG 精算格式 → 定量章通用，`mode: optional`
  - 净现金/MC>100% 特殊处理 → 条件触发

**判断标准**：新增规则时，问自己——"这条规则对茅台和万科都适用吗？"
- 是 → 放 agent prompt
- 否 → 放模板 ITEM_RULE，加 `facets_any`

**反模式**：不要在 agent prompt 里堆砌"若XX则YY"的条件判断。那是模板 ITEM_RULE 的职责。
| 可追溯 | citation_verifier 事后检查 | 来源清单自动聚合 |
