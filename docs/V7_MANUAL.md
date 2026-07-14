# 龟龟投资策略框架 V9.3 — 使用手册

> 最后更新：2026-07-12 | 版本：V9.3 保守主义引擎 (AA双轨 + PE硬上限 + M行业常识 + DPS口径分离 + 异常强制传播)

## 1. 框架是什么

龟龟投资策略框架是一个半自动化的基本面分析系统。输入一只港股或 A 股代码，输出一份包含 4 大类因子（因子1拆为 1A/1B/1C 三个子项，因子2/3/4各为单项）、DDM 估值、仓位建议、否决门检查的完整分析报告。

核心设计理念：**Python 负责会计数据的标准化提取和统计加工；LLM 负责需要商业判断的参数估算和叙事构建。** 边界不在"数字/文字"，而在"不需要判断的加工"和"需要判断的转化"之间。

## 2. 架构速览

```
stock_analysis.db（8,433只股票，2,919只港股，2005-2025，127,892条记录）
        │
        ├── Phase 0 (V9 新增) 前置诊断
        │   ├── pre_analysis_phase.py   → 断点检测 + CV分级 + 分析窗口
        │   └── pdf_page_locator.py     → PDF章节页码定位（TOC解析+附注扫描）
        │
        ├── Zone A (Python 确定性计算)
        │   ├── compute_bundle.py       → 原始因子值（GG, DDM, λ, 仓位, 否决门）
        │   │                              V9.2: --zone-j 消费 Zone J 参数精算
        │   ├── build_financial_trends.py → IS/BS/CF表 + 比率 + 趋势信号
        │   └── zone_d_industry_context.py → 行业分位 + 可比公司
        │         ↕  Zone J 精炼参数
        ├── Zone B (协调器直接读PDF提取定性 — V8.3+)
        │   │
        │   ├── Zone J (判断型参数化层 — LLM参与数字生产)
        │   │   └── zone_j_agent.py     → 护城河证据/Capex分类/收益质量/数据折价
        │   │
        ├── Zone C (LLM 报告写作)
        │   └── zone_c_chain.py         → C1→C2→C2b→C3→C3b→C4 六段式报告
        │
        └── 验证
            ├── citation_verifier.py    → 报告数字 vs JSON 源文件 + 参数引用链
            ├── boundary_validator.py   → JSON Schema 校验
            └── quality_gate.py         → 报告质量门禁
```

**V9.2 数据流**: Phase 0 诊断 → Zone A 初算（默认参数）→ Zone B 定性提取 → Zone J 参数估算 → Zone A 精算（`--zone-j` 消费 Zone J 参数）→ Zone C 报告

## 3. 快速开始

### 3.1 环境要求

- Python 3.10+
- SQLite3
- 约 2GB 磁盘空间（22 年港股数据）
- Tushare Pro token（可选，已有离线 CSV 数据包则不需要）

### 3.2 数据准备

数据位于 `hk_financials/` 目录，结构：

```
hk_financials/
├── hk_financials_2005/
│   ├── hk_basic_2005.csv
│   ├── hk_income_2005.csv
│   ├── hk_balancesheet_2005.csv
│   ├── hk_cashflow_2005.csv
│   └── hk_fina_indicator_2005.csv
├── hk_financials_2006/
│   └── ...
└── hk_financials_2026/
    └── ...
```

**导入数据**（只需执行一次）：

```bash
cd Turtle_investment_framework

# 导入全部 22 年数据到 stock_analysis.db
python3 scripts/import_hk_bulk.py --all --year 2005-2025

# 或只导入 stocks 表（3,488只股票基本信息）
python3 scripts/import_hk_bulk.py --stocks-only

# 或导入单只股票测试
python3 scripts/import_hk_bulk.py --code 00700.HK --year 2015-2025
```

导入后数据库状态验证：

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('stock_analysis.db')
print('Stocks:', conn.execute('SELECT COUNT(*) FROM stocks').fetchone()[0])
print('Financials:', conn.execute('SELECT COUNT(*) FROM annual_financials').fetchone()[0])
print('Years:', conn.execute('SELECT MIN(fiscal_year), MAX(fiscal_year) FROM annual_financials').fetchone())
conn.close()
"
# 预期输出: Stocks: 3488 | Financials: ~43000 | Years: 2005-2025
```

### 3.3 一键跑全流程

```bash
# 预览模式（看哪些层需要跑）
python3 scripts/run_pipeline.py --code 01502.HK --dry-run

# 实际执行
python3 scripts/run_pipeline.py --code 01502.HK
```

### 3.4 分步执行（V9 推荐流程）

```bash
# Step 0: 前置诊断 + PDF章节定位 (V9 NEW)
python3 scripts/pre_analysis_phase.py --code 00816.HK -v
# → output/{DIR}/analysis_contract.json（分析窗口、周期分类、三轨年份）

python3 scripts/pdf_page_locator.py \
  --pdf output/{DIR}/{CODE}_年报.pdf \
  --output output/{DIR}/page_map_{YEAR}.json -v
# → 定位每个章节的精确页码范围（MDA/关联交易/审计/附注等）

# Step 1: Zone A 定量计算
python3 scripts/compute_bundle.py --from-db --code 00816.HK --output output/{DIR}
python3 scripts/build_financial_trends.py --code 00816.HK
python3 scripts/zone_d_industry_context.py --code 00816.HK --output output/{DIR}

# Step 2: 数据打包
python3 scripts/build_data_pack.py --code 00816.HK

# Step 3: 协调器调度 4 个 sub-agent 并行读 PDF
# sub-agent-1..4: 各读一年 PDF → zone_b_{year}_partial.json
# 协调器汇总 4 个 partial → mda.json / segments.json / risks.json / governance.json / audit.json

# Step 4: 协调器调度 4 个 sub-agent 并行估算 Zone J 参数
python3 scripts/zone_j_agent.py --code 00816.HK --agent {agent} --save-prompt
# sub-agent-ZJ-1..4: 各自读 prompt → 输出参数 JSON（带 evidence_ref）
# 协调器验证: --validate 每条参数 → compute_bundle --zone-j

# Step 5: 协调器顺序调度 6 个 sub-agent 写 Zone C 报告
python3 scripts/zone_c_chain.py --code 00816.HK --save-prompts
# sub-agent-ZC-1..6: C1→C2→C2b→C3→C3b→C4 链式处理
# 协调器检查行数 → 拼装最终报告

# Step 6: 验证
python3 scripts/quality_gate.py --code 00816.HK
python3 scripts/citation_verifier.py --code 00816.HK
python3 scripts/boundary_validator.py --code 00816.HK --boundary zone_b
```

## 4. 目录结构

### 4.1 框架代码

```
Turtle_investment_framework/
├── stock_analysis.db                   # 核心数据库
├── scripts/
│   ├── import_hk_bulk.py               # L1: 批量数据导入
│   ├── migrate_to_db.py                # L2: 数据入库管道
│   ├── db_gate.py                      # L2: 入库门禁
│   ├── compute_bundle.py               # Zone A: 定量计算
│   ├── build_financial_trends.py       # Zone A: 财务趋势
│   ├── compute_bundle_precise.py       # Zone A: 精算（Zone J参数）
│   ├── zone_b_extractor.py             # Zone B: LLM提取框架
│   ├── build_report_context.py         # Zone B: 上下文（旧正则版）
│   ├── zone_j_agent.py                 # Zone J: 参数估算
│   ├── zone_c_chain.py                 # Zone C: 6-Agent报告链(V6)
│   ├── report_assembler.py             # Zone C: 报告组装+物理边界
│   ├── citation_verifier.py            # L5.5: 引用验证
│   ├── boundary_validator.py           # L5.5: Schema验证
│   ├── rule_engine.py                  # P3: 规则引擎
│   └── run_pipeline.py                 # 编排入口
├── docs/
│   ├── V5_ARCHITECTURE_PLAN.md         # 架构设计文档
│   └── V5_FRAMEWORK_MANUAL.md          # 本文件
└── output/{code}_{company}/            # 每个标的的输出目录
```

### 4.2 单标的输出目录（以 00816.HK 金茂服务为例）

```
output/00816_金茂服务/
├── analysis_contract.json               # V9: 前置诊断（断点/周期分类/三轨年份）
├── page_map_2025.json                   # V9: PDF章节页码映射
├── page_map_202{2-4}.json
│
├── compute_bundle.json                  # Zone A: 因子2/3/4定量+否决门
├── compute_bundle_precise.json          # Zone A: Zone J精算版
├── financial_trends.json                # Zone A: IS/BS/CF表+趋势信号
├── industry_context.json                # Zone A: 行业分位+可比公司
├── data_pack_agent.md                   # Phase 2.1: 定量数据汇总
│
├── mda.json                             # Zone B: MDA提取（管理层叙述+运营指标）
├── segments.json                        # Zone B: 分部毛利率+业态结构
├── risks.json                           # Zone B: 应收账龄+商誉减值
├── governance.json                      # Zone B: 关联方+治理
├── audit.json                           # Zone B: 审计师+意见+KAM+非经常项
│
├── moat_assessment.json                 # Zone J: 护城河证据+B类参数+g_base
├── capex_classification.json            # Zone J: Capex分类+增量ROIC
├── earnings_quality.json                # Zone J: AR质量+AP检查+非经常项分类
├── data_discount.json                   # Zone J: 数据质量折价
│
├── chain_context.json                   # Zone C: Agent间上下文传递
├── zone_c_C{1-4,2b,3b}_prompt.txt       # Zone C Agent prompt
├── zone_c_C{1-4,2b,3b}_output.md        # Zone C Agent 输出
├── 金茂服务_00816HK_分析报告_v7_final.md  # 最终报告
│
├── quality_gate_report.json             # 验证: 质量门禁
├── verification_report.json             # 验证: 引用验证
│
├── 00816.HK_202{2-5}_年报.pdf            # 年报PDF
├── pdf_sections_2025.json               # 年报PDF切片(pdfplumber)
├── pdf_full_text.json                   # 5年定性文本汇编
│
├── overrides.json                       # 人工覆盖（可选）
└── .pipeline_state.json                 # 管道状态
```

## 5. 各 Zone 说明

### Zone A — Python 确定性计算（V9.3 保守主义）

`compute_bundle.py` 不需要 LLM，直接从数据库查询并计算。V9.3 新增 4 项保守修正：

| 规则 | 说明 |
|------|------|
| **AA 双轨制** | AP/OCF > 30% 或 DPO 偏离 > 50% 时，自动计算 `aa_adjusted`（剥离营运资本异常波动） |
| **PE 硬上限** | 轻资产（capex/rev < 3%）无行业数据时，PE 上限强制 12x（而非 18x） |
| **M 行业常识** | 轻资产公司 M_samples=0 时，默认 M=0.70（而非 0.40） |
| **DPS 口径分离** | 分离 `dps_fy`（年报全年）和 `dps_ttm`（含特别股息），DDM 默认用 `dps_fy` |

`compute_bundle --zone-j` 消费 Zone J 的 LLM 参数估算结果，将精炼参数注入估值模型。

| 脚本 | 功能 | 输出 |
|------|------|------|
| `compute_bundle.py` | 计算因子2/3/4全部定量指标（默认参数） | compute_bundle.json |
| `compute_bundle.py --zone-j {DIR}` | 消费 Zone J 精炼参数，重新计算 | compute_bundle.json（覆盖） |
| `build_financial_trends.py` | 从DB拉取完整IS/BS/CF表，计算比率和趋势信号 | financial_trends.json |

### Zone B — 协调器直接读 PDF 提取定性（V8.3+）

**V8.3 推荐方式**：协调器（Claude Agent）直接按 `pdf_page_locator.py` 生成的页码映射精准 Read PDF 对应章节，提取定性内容，写入 Zone B JSON。

步骤：
1. `pdf_page_locator.py` 生成 PDF 章节页码映射（TOC解析 + 财务附注扫描）
2. 协调器按 page_map 页码范围 Read PDF
3. 协调器提取结构化定性数据 → mda/segments/risks/governance/audit.json

**提取内容**（只提取 data_pack_agent.md 中没有的定性数据）：

| 提取内容 | 目标文件 | 说明 |
|---------|---------|------|
| 管理层业绩解释 | mda.json | 为什么收入/利润变化？ |
| 前瞻指引+战略变化 | mda.json | Capex计划/战略目标/并购 |
| 运营指标(非财务) | mda.json | 在管面积/门店数/产能等 |
| 分部收入/毛利率 | segments.json | data_pack有总数,缺分部细节 |
| 应收账龄明细 | risks.json | 4档金额+占比+坏账计提政策 |
| 风险描述+缓释措施 | risks.json | 年报中列出的风险文字 |
| 商誉余额+减值 | risks.json | 如有 |
| 关联方交易详情 | governance.json | 前5大+交易性质+定价基础 |
| 审计意见+KAM | audit.json | 审计师/意见/关键审计事项 |
| 非经常项目明细 | audit.json | 逐项金额+性质+是否应扣除 |

**禁止提取**：营收/NP/OCF/Capex/毛利率/ROE/EPS/DPS——这些已在 data_pack_agent.md 中。

#### Zone B 旧自动化管道（fallback）

如果没有协调器（非 Claude 环境），可使用旧的自动化管道：

```bash
python3 scripts/pdf_preprocessor.py --pdf report.pdf  # pdfplumber提取全文
python3 scripts/build_full_text.py --code 00816.HK    # 5年定性文本汇编
python3 scripts/zone_b_v8.py --code 00816.HK --stage year --year 2025 --save-prompt
# → LLM 处理 prompt → zone_b_2025_partial.json
python3 scripts/zone_b_v8.py --code 00816.HK --stage master --write
# → 合并5年 → mda/segments/risks/governance/audit.json
```

**降级模式**：如果没有年报 PDF，Zone B 跳过。Zone C 报告标注"⚠️ 降级模式"。

**Schema 统一**：两种路径（协调器直读 / zone_b_v8 自动化管道）产出完全相同的 JSON schema。`boundary_validator.py --boundary zone_b` 可验证任意路径的产出是否符合规范。

### Zone J — 判断型参数化层 (V9.2 架构诚实化)

Zone J 是 LLM 参与数字生产的关键层。基于 Zone A 标准化数据 + Zone B 定性证据，估算估值模型所需的关键参数。

**每个参数必须附带**：`value`（参数值）、`rationale`（判断理由）、`evidence_ref`（证据引用，指向 Zone B JSON 的具体字段）、`confidence`（置信度 high/medium/low）、`override`（是否人工覆盖）。

| Agent | 输出 | 关键参数 | 被谁消费 |
|-------|------|------|------|
| moat | moat_assessment.json | b_penalty_final, g_base, g_scenarios, moat_evidence | `compute_bundle --zone-j` |
| capex | capex_classification.json | mcapex_split_pct, growth_classification, incremental_roic | `compute_bundle --zone-j` |
| earnings_quality | earnings_quality.json | ar_quality, ap_excess_check, non_recurring_items | `compute_bundle --zone-j` |
| data_quality | data_discount.json | total_discount_pct, confidence_by_section | `compute_bundle --zone-j` |

**架构契约**：Zone J 只输出参数+证据+置信度，不输出"护城河评级=窄"等结论性字段。Zone C 能看到"为什么 b_penalty=0.25"（via evidence_ref），但看不到预制的评级结论——Zone C 必须自己从证据推导。

**降级模式**：如果没有 Zone B，Zone J 跳过。`compute_bundle --zone-j` 使用默认参数（g_base=2.0%, b_penalty=0.25）。

### Zone B+ — Web Research（V7 新增）

`scripts/zone_b_plus_websearch.py` 生成结构化搜索 prompt，LLM 执行 WebSearch 获取同业数据/管理层/行业动态，输出 `web_research.json`（带 source_url，缓存 30 天）。

### Zone C — LLM 报告写作

6 个 Agent 顺序执行（V7），每个专注单一因子。Agent 只能读取其 allowed_inputs 列表中的 JSON 文件（含 V7 新增的 `pdf_full_text.json`、`web_research.json`、` calculation_trace`），物理上无法访问原始 PDF 或 DB。

**链序**：C1 → C2 → C2b → C3 → C3b → C4

| Agent | 负责章节 | 核心新增输入（V7） |
|-------|---------|---------|
| C1 | 报告头+财务趋势+因子1A+1B(10模块) | pdf_full_text(190K定性), web_research, industry_context(target_metrics+peers) |
| C2 | 因子1C:增量增长检验 | pdf_full_text |
| C2b | 因子2:穿透回报率粗算 | calculation_trace.factor2_* |
| C3 | 因子3:步骤1-7(AA→GG) | calculation_trace.factor3_gg_raw/gg |
| C3b | 因子3:步骤8-13 + 跨因子回验 | chain_context(前序Agent判断), calculation_trace |
| C4 | 因子4+综合输出+风险提示 | chain_context(全量), calculation_trace.factor4_ddm |

**V7 关键机制**：
- **模块〇参数锚定**：C1 输出 6 块参数表，全报告 `（模块〇X 项）` 引用
- **calculation_trace**：每步展示 formula→substitutions→steps→result
- **chain_context**：每个 Agent 输出 `CHAIN_CONTEXT:` 块，C3b 回验定性判断

### L5.5 — 验证

| 脚本 | 功能 | 输出 |
|------|------|------|
| `citation_verifier.py` | 从报告MD提取所有数字，对照9个JSON源文件验证 | verification_report.json (PASS/WARN/FAIL) |
| `boundary_validator.py` | 验证Zone B/J/A JSON符合schema | 终端输出 (PASS/FAIL) |

## 6. 关键概念

### 6.1 自适应分析时域（V9 新增）

框架不再硬编码"近5年"。Phase 0 前置诊断模块 (`pre_analysis_phase.py`) 自动确定分析窗口：

1. **结构性断点检测**：商誉跳涨 > 20% 或总资产突变 > 50% → 重置分析起点
2. **双维度周期分类**：利润 CV（供给端波动）× 需求驱动类型（行业关键词） → 确定窗口 N（5-10年）
3. **利润平滑反证**：利润CV < 1.0 且平滑系数 > 10% → 自动降一档
4. **三轨并行**：轨道A（长期·因子1B）、轨道B（周期定位·因子2）、轨道C（边际·因子1C，固定5年）

输出 `analysis_contract.json`，供所有下游 Zone 读取动态年份列表。

详见 `docs/ANALYSIS_HORIZON.md`。

### 6.2 降级模式

如果某个 Zone 的输入不存在，框架自动降级：
- **Phase 0 不可用**（无 analysis_contract） → 回退到固定5年窗口
- **PDF 不可用** → Zone B 跳过，Zone C 仅用定量数据，标注"⚠️ 降级模式"
- **PDF < 3 年可用** → 标注 ⚠️，汇总 Agent 只处理可用年份
- **page_map 章节缺失** → 协调器手动翻阅 PDF 目录页定位
- **PDF 文字层损坏**（CJK重复） → `is_garbled()` 自动检测，跳过损坏页
- **Zone B 有但 Zone J 输入不全** → 跳过 Zone J，使用默认参数（g_base=2.0%, b_penalty=0.25）

### 6.3 物理数据边界

Zone C 的 prompt 构建代码（`report_assembler.py`）只能读取白名单中的 9 个 JSON 文件。Zone C 的 LLM 物理上无法访问原始 PDF、CSV 或 DB。这是架构级硬约束，不是 prompt 级软约束。

### 6.4 数字来源规则

- **因子 2/3/4 定量**：只能从 compute_bundle.json 引用。禁止 LLM 自行计算。
- **财务趋势表**：只能从 financial_trends.json 引用。
- **运营/治理/风险事实**：只能从 Zone B/J JSON 引用。
- 违反以上规则 → citation_verifier 检测到 → 报告标注 WARN。

### 6.5 参数溯源

Zone J 的每个参数必须附带 `evidence_ref`，指向 Zone B JSON 中支持该判断的具体字段。`citation_verifier.py` 验证每个参数的引用链是否完整。`override: true` 的参数（人工覆盖）跳过此检查。

### 6.6 人工覆盖（overrides.json）

如果对 Zone J 的参数有异议，可以在 `output/{code}_{company}/overrides.json` 中手动覆盖：

```json
{
  "moat_assessment": {
    "b_penalty_final": 0.30,
    "_reason": "非商务物业占比上升速度比预期快，上调B类惩罚"
  }
}
```

下次运行 `compute_bundle_precise.py` 时会优先使用覆盖值。

## 7. 当前限制与已知问题

### 7.1 自适应分析时域 V1 局限

- 断点检测仅基于 DB 财务数据，无法检测纯业务结构变化（需 Zone B 分部数据）
- CV 分级无法区分"增长驱动的高CV"和"周期驱动的高CV"
- 上市 < 5 年的公司，三轨退化为单轨
- compute_bundle 内部仍用硬编码 3y/5y，尚未对接 contract 动态窗口（V2 待实现）

### 7.2 Zone B 依赖年报 PDF

没有年报 PDF 就无法获取定性素材。港股 PDF 的 CJK 字符重复（pdfplumber bug）可能导致部分章节文字质量下降。用 `pdf_page_locator.py` + 协调器精准读页可绕过此问题。

### 7.3 协调器 Read PDF 需 Claude 环境

V8.3 协调器直接 Read PDF 的方式在 DeepSeek 等纯文本环境下不可用（PDF 页渲染为图片，纯文本模型无法识别）。降级方案：pdfplumber 抽文字 → 协调器读文本。

### 7.4 Zone J 需要 LLM 手动处理

Zone J agent 输出 prompt 后，需要手动让 LLM 处理并保存结果。

### 7.5 EV 口径未实现（已有止损）

当净现金/市值 > 40% 时，DDM 估值可能不适用。`compute_bundle.py` 已计算 `net_cash_pct_mc`，并在 >40% 时输出 `valuation_warning` 字段。Zone C 可读取此字段在报告中标注警告。尚未实现自动切换到 EV 口径。

## 8. 常用命令速查

```bash
# Phase 0: 前置诊断 + PDF章节定位 (V9)
python3 scripts/pre_analysis_phase.py --code 00816.HK -v
python3 scripts/pdf_page_locator.py --pdf output/{DIR}/{CODE}_年报.pdf -v

# Phase 0.5: 年报下载
python3 scripts/download_report.py --stock-code 00816.HK --report-type 年报 --year 2025 --auto
python3 scripts/download_report.py --stock-code 00816.HK --report-type 年报 --year 2025 --hk

# Zone A: 定量计算
python3 scripts/compute_bundle.py --from-db --code 00816.HK --output output/{DIR}
python3 scripts/build_financial_trends.py --code 00816.HK
python3 scripts/zone_d_industry_context.py --code 00816.HK --output output/{DIR}
python3 scripts/compute_bundle_precise.py --code 00816.HK

# Phase 2.1: 数据打包
python3 scripts/build_data_pack.py --code 00816.HK

# Zone B: 协调器按 page_map 读 PDF → 提取定性 → 写 Zone B JSON
# （协调器 = Claude Agent，手动执行）

# Zone B fallback: 自动化管道 (非Claude环境)
python3 scripts/pdf_preprocessor.py --pdf report.pdf
python3 scripts/build_full_text.py --code 00816.HK
python3 scripts/zone_b_v8.py --code 00816.HK --stage year --year 2025 --save-prompt

# Zone J (生成 LLM prompt)
python3 scripts/zone_j_agent.py --code 00816.HK --agent moat --save-prompt

# Zone C
python3 scripts/zone_c_chain.py --code 00816.HK --save-prompts
python3 scripts/zone_c_chain.py --code 00816.HK --assemble

# 验证
python3 scripts/quality_gate.py --code 00816.HK
python3 scripts/citation_verifier.py --code 00816.HK
python3 scripts/boundary_validator.py --code 00816.HK --boundary zone_b

# 管道
python3 scripts/run_pipeline.py --code 00816.HK --dry-run
python3 scripts/run_pipeline.py --code 00816.HK

# 数据导入
python3 scripts/import_hk_bulk.py --all --year 2005-2025
```
