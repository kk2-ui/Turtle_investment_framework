# Turtle V12 使用手册

> Dayu 定性深度分析 + Turtle 定量估值框架 → 单 Agent 全自动生成

## 快速开始

```bash
cd Turtle_investment_framework

# 完整流程（从零开始：下载年报 → 定量计算 → Agent 写作）
export DEEPSEEK_API_KEY="sk-xxx"
PYTHONPATH=scripts:$PYTHONPATH python3 scripts/turtle_agent/run.py \
  --code 01502 --unified

# 跳过数据准备（已有 compute_bundle + PDF）
PYTHONPATH=scripts:$PYTHONPATH python3 scripts/turtle_agent/run.py \
  --code 01502 --unified --skip-prepare --output output/01502_金融街物业

# 仅定性分析（不做估值）
PYTHONPATH=scripts:$PYTHONPATH python3 scripts/turtle_agent/run.py \
  --code 01502 --qualitative-only --skip-prepare --output output/01502_金融街物业
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--code` | 股票代码（01502 / 600519.SH / 00700.HK） | 必填 |
| `--unified` | V12 模式：Dayu 定性 + Turtle 定量 | — |
| `--skip-prepare` | 跳过 Phase 0-2（数据已就绪） | — |
| `--qualitative-only` | 仅定性分析（Ch1-9，不估值） | — |
| `--output` | 输出目录 | `output/{code}` |
| `--dry-run` | 仅 Python 计算，不调 LLM | — |
| `--max-iter` | Agent 最大迭代次数 | 30 |
| `--template` | 报告模板路径 | `templates/report_template_v12.md` |

**LLM Provider 自动检测**：
- 设置 `DEEPSEEK_API_KEY` → 走 DeepSeek OpenAI 兼容 API（httpx 直调）
- 设置 `ANTHROPIC_API_KEY`（`sk-ant-` 开头）→ 走 Anthropic API
- 都不设 → 生成 prompt 文件，需手动处理

---

## 数据来源

### 数据库（Phase 0-1）

| 数据 | 来源 | 格式 |
|------|------|------|
| 财务三表 | `stock_analysis.db` → `annual_financials` 表 | SQLite，8,433 只股票，2005-2025 |
| 股票基本信息 | `stock_analysis.db` → `stocks` 表 | 总股本、行业、上市日期 |
| 行业分类 | `stock_analysis.db` → `industry_classification` | L1/L2 行业 |

数据更新：`scripts/tushare_modules/` 下的 Python 脚本从 Tushare Pro API 采集。

### 年报 PDF（Phase 0.5）

| 市场 | 下载器 | API |
|------|--------|-----|
| A 股 | `scripts/downloaders/cninfo.py` | 巨潮资讯 |
| 港股 | `scripts/downloaders/hkexnews.py` | 披露易 |
| 美股 | `scripts/downloaders/sec.py` | SEC EDGAR |

### 定量计算输出（Phase 1-2）

| 文件 | 内容 |
|------|------|
| `compute_bundle.json` | 因子2/3/4 完整参数（NP/OE/AA/GG/DDM/否决门） |
| `financial_trends.json` | 5 年三表趋势 + ROE/毛利率/CAGR |
| `industry_context.json` | 行业百分位 + 可比同行列表 |
| `analysis_contract.json` | 分析窗口 + 周期分类 |
| `mda.json` | MD&A 管理层讨论提取 |
| `segments.json` | 业务分部收入/毛利率 |
| `risks.json` / `governance.json` / `audit.json` | 定性 JSON |

---

## 架构

```
┌──────────────────────────────────────────────────────────┐
│  python -m turtle_agent.run --code 01502 --unified       │
└─────────────────────┬────────────────────────────────────┘
                      │
    ┌─────────────────┴──────────────────┐
    │  Phase 0-2: Python 数据准备 (~10s)   │
    │  • pre_analysis_phase.py           │
    │  • download_report.py              │
    │  • compute_bundle.py               │
    │  • pdf_page_locator.py             │
    │  → 30+ JSON + 5 PDF               │
    └─────────────────┬──────────────────┘
                      │
    ┌─────────────────┴──────────────────┐
    │  Agent Loop: LLM 全自动 (~20min)     │
    │  • _load_context() → 加载全部数据    │
    │  • _build_system_prompt() → V12 指令 │
    │  • _run_loop() → 最多 80 轮迭代      │
    │    ├─ 数据发现 (list_documents)      │
    │    ├─ 定性写作 Ch1-9 (write_chapter) │
    │    ├─ 审计修复 (audit_chapter)       │
    │    ├─ 定量写作 Ch10-13               │
    │    └─ 组装报告 (assemble_report)     │
    │  → 01502_分析报告_v12.md            │
    └──────────────────────────────────────┘
```

### Agent 工具集（20 个工具）

| 类别 | 工具 | 功能 |
|------|------|------|
| 读取 | `list_documents` | 列出所有可用数据和 PDF |
| | `get_financial_trends` | 获取 5 年财务趋势 |
| | `get_financial_statement` | 获取标准化财务报表 |
| | `read_zone_data` | 读取 Zone B 定性 JSON |
| | `read_section` | 读取 PDF 特定章节 |
| | `search_report` | 全文搜索年报关键词 |
| | `get_peer_comparison` | 同行对比（从 DB 读取） |
| | `get_market_data` | 市场数据 + yfinance 股本修正 |
| 计算 | `compute_aa` | AA (FCF) 逐年构建链路 |
| | `compute_gg` | GG 穿透回报率（含股本修正） |
| | `compute_ddm` | DDM 五档估值 |
| | `compute_data_quality` | 数据完整性得分 |
| | `assess_moat` | 护城河评级 |
| | `evaluate_decision` | 综合决策（GG vs II） |
| 写作 | `write_chapter` | 写入章节（自动审计） |
| | `audit_chapter` | 审计章节（Dayu P1-P3 规则） |
| | `read_chapter` | 读取已写章节 |
| | `assemble_report` | 组装最终报告 |
| Phase | `run_pre_analysis` | 前置诊断 |
| | `download_annual_reports` | 下载年报 |
| | `compute_bundle_db` | 定量计算 |

### 报告结构（15 章）

```
Ch0:  投资要点概览（最后写，综合全局）
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
Part B: 量化投资判断（Turtle 方法论）
  Ch10: 增长质量与参数校准
  Ch11: 穿透回报率 GG
  Ch12: DDM 估值与仓位建议
Part C: 综合决策
  Ch13: 定性 × 定量 → 5 状态合成
  来源清单
```

---

## 质量体系

### 审计规则（Dayu 移植，3,844 行）

| 规则 | 说明 | 违规处理 |
|------|------|---------|
| P1 | 章节结构与骨架不匹配 | REGENERATE |
| P2 | 内容过短（定性<80行，定量<120行） | REGENERATE |
| P3 | 缺少"### 证据与出处"小节 | REGENERATE |
| S1 | 占位符残留 | PATCH / REGENERATE |
| E1 | 证据锚点密度不足 | PATCH |
| C2 | 涉及禁止内容 | PATCH / REGENERATE |
| S2 | 关键参数数值不一致 | PATCH |

### 条件化写作规则（193 条 ITEM_RULE）

来自 Dayu 模板，每条带 `facets_any` 条件。公司匹配到特定业务类型（如"平台互联网"）或约束（如"高资本开支"）时才触发对应规则，不匹配的不输出也不占位。

### 质量门禁（组装后）

| 检查 | 说明 |
|------|------|
| quality_gate | 9 项（占位符/表格数/关键参数/变量残留） |
| enhanced_quality_gate | 5 项（数值一致性/结论一致性/风险披露/Token效率） |
| evidence_citation | [source:] 锚点真实性验证 |
| data_gap_scanner | ⚠️ 标记分类 |
| 行数检查 | <800 行 → 不通过 |

### 决策框架

5 状态合成矩阵（Dayu 定性 × Turtle 定量）：

| | Turtle Buy | Turtle Hold | Turtle Avoid |
|---|---|---|---|
| **Dayu Continue** | Strong Buy | Cautious Watch | 好公司太贵 |
| **Dayu Pause** | 价格错配 | Hold Review | Likely Avoid |
| **Dayu Abandon** | 数据冲突 | Slow Fade | Strong Reject |

**决策优先级**：定量（GG/DDM/否决门）为第一优先。定性只能调整仓位，不能在定量否决时"拉回"决策。

---

## Prompt 瘦身原则

新增分析规则时，先判断——**这条规则对茅台和万科都适用吗？**

- **是** → 放 `agent_loop.py:_build_system_prompt()`
- **否** → 放 `report_template_v12.md` 的 ITEM_RULE，加 `facets_any` 条件

**反模式**：不要在 agent prompt 里堆砌"若 XX 则 YY"的条件判断。那是模板 ITEM_RULE 的职责。

---

## 渲染

```bash
# HTML 渲染（经典财经出版风格，衬线字体，暗红 accent）
PYTHONPATH=scripts:$PYTHONPATH python3 scripts/render_report.py \
  output/01502_金融街物业/01502_分析报告_v12.md --format html

# PDF（需 Chrome headless）
PYTHONPATH=scripts:$PYTHONPATH python3 scripts/render_report.py \
  output/01502_金融街物业/01502_分析报告_v12.md --format pdf
```

---

## 关键文件索引

| 文件 | 说明 |
|------|------|
| `scripts/turtle_agent/run.py` | 统一入口 |
| `scripts/turtle_agent/agent_loop.py` | Agent 核心 + system prompt 构建 |
| `scripts/turtle_agent/llm_client.py` | LLM API（Anthropic/DeepSeek/OpenAI） |
| `scripts/turtle_agent/tools/read_tools.py` | 数据读取工具（8 个） |
| `scripts/turtle_agent/tools/calc_tools.py` | 计算工具（6 个：AA/GG/DDM/质量/护城河/决策） |
| `scripts/turtle_agent/tools/write_tools.py` | 写作+审计+组装工具（4 个） |
| `templates/report_template_v12.md` | V12 报告模板（15章 + FACET_CATALOG + 193 ITEM_RULE） |
| `scripts/audit_rules.py` | Dayu 审计系统（P1-P3 + S1 + E1 + C2 + S2） |
| `scripts/audit_formatting.py` | 审计格式化（标题提取/结构匹配/证据小节） |
| `scripts/audit_enums.py` | 审计枚举（13 条规则码 + 修复策略） |
| `scripts/repair_executor.py` | 修复执行器 |
| `scripts/company_facets.py` | Facet 过滤引擎（36 业务类型 + 25 约束） |
| `scripts/models.py` | 数据模型（ChapterTask/Contract/ItemRule/FacetProfile） |
| `scripts/unified_decision_synthesizer.py` | 5 状态合成矩阵 |
| `scripts/render_report.py` | 多格式渲染（HTML/PDF/DOCX） |
| `config/scenes.yaml` | LLM 场景温度配置 |
