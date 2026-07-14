# 龟龟投资策略 V10 — 协调器

> 本文件与 `scripts/run_pipeline.py` 步骤一一同步。
> `run_pipeline.py` 是可执行真源 — 所有自动化步骤通过它运行。
> **⚡手动** 标记的步骤需要协调器调度 LLM sub-agent。

## 管道总览

```
Step 0    Phase 0   前置诊断          auto   pre_analysis_phase.py
Step 0.5  Phase 0.5 年报下载          auto   download_report.py --all-years  [阻断门:<3年阻断]
Step 1    Phase 1   Zone A 定量       auto   compute_bundle + financial_trends
Step 1.5  Phase 1   行业数据          auto   zone_d_industry_context.py
Step 2    Phase 2   Zone B 定位       auto   pdf_page_locator.py (每份年报)
Step 2.5  Phase 2   Zone B LLM提取    ⚡手动  协调器调度 sub-agent 读PDF→5个JSON
Step 3    Phase 3   Zone J prompts    auto   zone_j_agent.py ×4
Step 3.5  Phase 3   Zone J LLM处理    ⚡手动  协调器调度 4个 sub-agent 并行
Step 4    Phase 3   Zone A 精算       auto   compute_bundle.py --zone-j
Step 4.5  Phase 3   规则引擎          auto   rule_engine.py
Step 5    Phase 4   Zone C V10写管线  auto   write_pipeline.py (含审计循环)
Step 6    Phase 5   质量门禁          auto   quality_gate + enhanced
Step 6.5  Phase 5   溯源验证          auto   citation_verifier ×2
```

## 快速开始

```bash
# 自动推进到下一个未完成步骤
python3 scripts/run_pipeline.py --code 03990.HK

# 查看进度
python3 scripts/run_pipeline.py --code 03990.HK --status

# 从断点继续
python3 scripts/run_pipeline.py --code 03990.HK --resume

# 只运行特定步骤
python3 scripts/run_pipeline.py --code 03990.HK --step 5
```

---

## Step 0 — Phase 0：前置诊断 (auto)

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 0
# → pre_analysis_phase.py → analysis_contract.json
```

产出：`analysis_contract.json`（effective_years, cyclicality_profile, three_track, anomaly_flags）

---

## Step 0.5 — Phase 0.5：年报批量下载 (auto) 🔴阻断门

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 0.5
# → download_report.py --hk --all-years
```

**4级回退链**：cre8ir → hkexnews API → cninfo → hkexnews legacy scan

**阻断规则**：下载完成后自动检查 `*_年报.pdf` 数量。
- **< 3 年**：❌ 阻断，管道停止。需手动补充 PDF。
- **≥ 3 年**：✅ 自动进入下一步。

**下载后验证**：每份 PDF 检查文件大小 ≥ 2MB + 内容含年报关键词。通知信函/申请表格自动排除并重试。

**A股**：将 `--hk` 替换为 `--auto`，同时指定 `--stock-code SH/SZ{CODE}`。

---

## Step 1 — Phase 1：Zone A 定量计算 (auto)

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 1
# → compute_bundle.py --from-db → compute_bundle.json
# → build_financial_trends.py → financial_trends.json
```

HK 股票自动通过 yfinance 获取股价和股本。若 yfinance 不可用，需手动传入 `--price` 和 `--shares`。

---

## Step 1.5 — Phase 1：行业数据 (auto)

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 1.5
# → zone_d_industry_context.py → industry_context.json
```

---

## Step 2 — Phase 2：Zone B PDF 定位 (auto)

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 2
# → pdf_page_locator.py 对每份年报生成 page_map_{YEAR}.json
```

---

## Step 2.5 — Phase 2：Zone B LLM 定性提取 ⚡手动

**协调器调度 sub-agent**：

```
sub-agent-ZB: 用 pdfplumber 按 page_map 读取 PDF 指定章节。
  每个年度提取:
    mda.json       — 管理层讨论、收入/利润驱动、展望、运营指标
    segments.json  — 分部收入/毛利率
    risks.json     — 风险描述+缓释措施
    governance.json — 董事会、关联方、控股股东
    audit.json     — 审计师、审计意见、KAM、非经常项目
  约束: 金额百万元RMB，缺失标"data not available"，禁止编造
```

**协调器检查**：
- mda/segments/risks/governance/audit.json 均存在
- 每文件有实质内容（>200 bytes）
- `boundary_validator.py --boundary zone_b` 通过

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 2.5
# 检查 Zone B JSON 是否就绪
```

---

## Step 3 — Phase 3：Zone J 参数化 Prompt 生成 (auto)

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 3
# → zone_j_agent.py --agent {moat,capex,earnings_quality,data_quality} --save-prompt
```

---

## Step 3.5 — Phase 3：Zone J LLM 参数估算 ⚡手动

**协调器并行调度 4 个 sub-agent**：

| Agent | 输入 | 输出 | 关键参数 |
|-------|------|------|---------|
| moat | zone_j_prompt_moat.txt | moat_assessment.json | b_penalty, g_base, g_scenarios, 价值陷阱信号 |
| capex | zone_j_prompt_capex.txt | capex_classification.json | mcapex_split_pct, growth_classification |
| earnings_quality | zone_j_prompt_earnings_quality.txt | earnings_quality.json | AR质量, 非经常项目, OCF质量 |
| data_quality | zone_j_prompt_data_quality.txt | data_discount.json | total_discount_pct, 字段完整性, 口径连续性 |

**每个参数格式**：`{value, rationale, evidence_ref, confidence}`

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 3.5
# 检查 Zone J JSON 是否就绪 + boundary_validator
```

---

## Step 4 — Phase 3：Zone A 精算 (auto)

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 4
# → compute_bundle.py --zone-j（消费 b_penalty/g_base/mcapex_split/data_discount）
# → GG/DDM/λ 使用 Zone J 精炼参数重新计算
```

---

## Step 4.5 — Phase 3：规则引擎 (auto)

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 4.5
# → rule_engine.py → rule_engine_signals.json
```

---

## Step 5 — Phase 4：Zone C V10 写管线 (auto)

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 5
# → write_pipeline.py（自动完成以下全部）:
```

**管线内部流程**（无需协调器干预）：

```
前置检查(PDF≥3, ZoneB≥3/5, compute_bundle)
  → 模板解析+验证 (9章)
  → 并行写作+审计 (6章, ThreadPoolExecutor)
    每章: 写 → 审(S1/S2/E1/C1/C2) → 修(patch/regenerate) → 再审
  → 决策章 (Continue/Hold/Abandon)
  → Executive Summary 回填
  → 来源清单 (分类聚合)
  → 最终组装 → {公司名}_{代码}_分析报告_v10.md
  → 增强质量门禁 → enhanced_quality_report.json
  → 执行追踪 → run_summary.json
```

**产出**：
- `{公司名}_{代码}_分析报告_v10.md`（最终报告）
- `run_summary.json`（执行追踪：逐章状态、证据数、耗时）
- `enhanced_quality_report.json`（数值一致性、风险披露、结论对齐）

---

## Step 6 — Phase 5：质量门禁 (auto)

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 6
# → quality_gate.py（结构检查：章节完整性、行数、表格数）
# → enhanced_quality_gate.py（内容检查：数值一致性、结论对齐、风险披露）
```

---

## Step 6.5 — Phase 5：溯源验证 (auto)

```bash
python3 scripts/run_pipeline.py --code {CODE} --step 6.5
# → citation_verifier.py（数字溯源：报告数字 vs compute_bundle）
# → citation_verifier.py --evidence-only（证据覆盖：锚点密度、未知来源）
```

---

## 硬约束

1. 协调器只调度 sub-agent，不亲自读 PDF 或处理 prompt
2. Zone B 并行（4 个年度 sub-agent）、Zone J 并行（4 个参数 sub-agent）
3. Zone C V10 管线自动完成写作+审计+组装
4. V10 新增：每个数据断言需 `[source: 文件名]` 证据锚点
5. V10 新增：每章通过审计（无 S1 error）后方可进入组装
6. Step 0.5 年报 < 3 年 → 阻断，不得继续
7. 不达标 → 重试，仍不达标 → 标注 ⚠️ 继续，不阻塞管道
8. `--legacy` 可回退 V9 单体 C_FULL 模式

## 降级处理

| 异常 | 处理 |
|------|------|
| 年报 < 3 年 | ❌ 阻断管道 |
| hkexnews 封锁 | 自动回退 cninfo |
| 下载文件为通知信函 | 自动排除+重试 |
| Zone B < 3 年可用 | 标注 ⚠️，只处理可用年份 |
| Zone J 输入缺失 | 使用默认值（g_base=2.0%, b_penalty=0.25） |
| Zone C 某章审计失败 | 标注 ⚠️，不阻塞其他章节 |
| yfinance 不可用 | 手动输入 --price --shares |
