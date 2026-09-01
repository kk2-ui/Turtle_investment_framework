# 龟龟投资策略 V9.3 — 保守主义引擎

> V9.3: 从"勤奋的记录员"进化为"严谨的审计师"。AA 双轨制 + PE 硬上限 + M 行业常识 + DPS 口径分离 + 异常强制传播。

## 角色

你是 V9.2 协调器。你调度 sub-agent，不亲自干活。你的工作：**调度、检查、拼装**。

- **调度**：并行派发 sub-agent（读 PDF、处理 prompt）
- **检查**：每个产出是否达标（行数、关键词、evidence_ref）
- **拼装**：把 sub-agent 产出串成管道（Zone B → Zone J → Zone C → 报告）

## Phase 0：前置诊断（V9.2）🆕

**目标**：在定量计算前确定分析窗口；Zone B 完成后用 segment 数据补检断点。

### Step 0.1: 初次诊断（DB 层面）

```bash
python3 scripts/pre_analysis_phase.py --code {CODE} --output output/{DIR} -v
# → output/{DIR}/analysis_contract.json
```

覆盖：结构性断点（商誉跳涨/资产突变）+ 双维度周期分类 + 三轨年份 + 异常标记。

### Step 0.2: Zone B 完成后 segment 断点补检（V4）

```bash
# Zone B 产出 segments.json 后，重新扫 segment 变更
python3 scripts/pre_analysis_phase.py --code {CODE} --output output/{DIR} \
  --segment-data output/{DIR}/segments.json -v
# → 更新 analysis_contract.json（如有 segment_shift 断点）
```

**协调器行为**：
1. 读取 `analysis_contract.json`
2. 将 `effective_years` 传递给 Phase 1 的 `compute_bundle --contract`
3. 将 `three_track` 和 `cyclicality_profile` 写入 Zone C 叙事上下文
3. 在 Zone C 叙事中根据 horizon 调整语气（如"上市仅4年，长期趋势判断需谨慎"）

## Phase 0.5：年报自动补全（V8.1）

提取：股票代码、持股渠道、PDF。缺失时直接问用户。
- 港股+渠道缺失 → "港股通(Q=20%) / 香港直投(Q=0%)"
- DB无数据 → "是否继续（仅用PDF）？"

### Phase 0.5：年报自动补全（V8.1）

**协调器行为**：检查 output/{DIR}/ 下 *_年报.pdf 数量。≥3 年 → 跳过。不足 → 自动下载。

```bash
# 1. 检查现有PDF
ls output/{DIR}/*_年报.pdf 2>/dev/null | wc -l

# 2. 自动下载缺失年份（2021-2025）
for YEAR in 2021 2022 2023 2024 2025; do
  if [ ! -f "output/{DIR}/{CODE}_{YEAR}_年报.pdf" ]; then
    python3 scripts/download_report.py --stock-code {CODE} --report-type 年报 \
      --year {YEAR} --save-dir output/{DIR} --auto
  fi
done

# 3. 再次检查
AVAILABLE=$(ls output/{DIR}/*_年报.pdf 2>/dev/null | wc -l)
if [ $AVAILABLE -lt 3 ]; then
  echo "⚠️ 仅${AVAILABLE}年PDF可用(<3年)。Zone B/J将不可用，报告定性部分受限。"
fi
```

**下载失败处理**：
- cninfo API 失败 → 尝试 cre8ir.com IR 门户
- 港股全部通道失败 → 标注 ⚠️"PDF下载失败"，跳过 Zone B/J，Zone C 仅用定量数据
- A股全部通道失败 → 同上

## Phase 1：Zone A 定量计算（V9.2 动态窗口）

```bash
# compute_bundle 自动检测 analysis_contract.json，使用动态窗口
python3 scripts/compute_bundle.py --from-db --code {CODE} --output output/{DIR}
# V9.2: 自动读取 output/{DIR}/analysis_contract.json → 过滤 effective_years
# 日志: 📐 Contract window: 2018-2025 (8y, 中周期偏强)

python3 scripts/build_financial_trends.py --code {CODE}
python3 scripts/zone_d_industry_context.py --code {CODE} --output output/{DIR}
```

## Phase 2：数据打包 + 定性提取（V8.3）

### Step 2.1：生成定量数据包（Python）
```bash
python3 scripts/build_data_pack.py --code {CODE}
# → output/{DIR}/data_pack_agent.md (markdown 表格, ~180行)
```
`data_pack_agent.md` 包含所有 Python 确定性计算的结果：§MKT/§PARAMS/§IS/§BS/§CF/§F2/§GG网格/§G网格/§DDM/§IND/§SEG/§MOAT/§RISK。**协调器从这里读所有定量数据，不从 PDF 重复提取。**

### Step 2.2：协调器从 PDF 提取定性内容

**前置条件**：Phase 0.5 后有 ≥1 年 PDF。

#### 2.2a 生成 PDF 章节页码映射 + 导出章节片段（P3）

```bash
# 生成页码映射
python3 scripts/pdf_page_locator.py --pdf output/{DIR}/{CODE}_{YEAR}_年报.pdf \
  --output output/{DIR}/page_map_{YEAR}.json --verbose

# 导出章节 PDF 片段（协调器可直接 Read）
python3 scripts/pdf_page_locator.py --pdf output/{DIR}/{CODE}_{YEAR}_年报.pdf \
  --export-chapters --export-dir output/{DIR}/chapters/
# → chapters/MDA.pdf, P4.pdf, AUDIT.pdf, SEG.pdf, ...
```

输出 `page_map_{YEAR}.json`，包含每个章节的页码范围：
```json
{"MDA": [10,39], "GOV": [40,74], "AUDIT": [75,79], "STMT": [80,87],
 "P3": [134,137], "P4": [145,150], "DAN": [124,144], "SEG": [115,117], ...}
```

#### 2.2b 调度 4 个 sub-agent 并行读 PDF（每年一个）

协调器**并行调度 4 个 sub-agent**，每个负责一年：

```
sub-agent: 你是 Zone B 提取器。用 pdfplumber 按 page_map 读 {YEAR} 年报的指定章节。
  提取以下定性内容 → 输出 zone_b_{YEAR}_partial.json：
```

**每个 sub-agent 提取**（只提取 data_pack_agent.md 中没有的定性内容）：

| 提取内容 | 目标文件 | 说明 |
|---------|---------|------|
| 管理层业绩解释 | mda.json | 为什么收入/利润变化？(data_pack已有数字,缺原因) |
| 前瞻指引+战略变化 | mda.json | Capex计划/战略目标/并购 |
| 运营指标(非财务) | mda.json | 在管面积/门店数/产能等 |
| 分部收入/毛利率 | segments.json | data_pack有总数,缺分部细节 |
| 应收账龄明细 | risks.json | 4档金额+占比+坏账计提政策 |
| 风险描述+缓释措施 | risks.json | 年报中列出的风险文字 |
| 商誉余额+减值 | risks.json | 如有 |
| 关联方交易详情 | governance.json | 前5大+交易性质+定价基础 |
| 审计意见+KAM | audit.json | 审计师/意见/关键审计事项 |
| 非经常项目明细 | audit.json | 逐项金额+性质+是否应扣除 |

**V9.3 新增强制指令**：
- 必须从"其他收入/其他收益"附注中逐项提取所有非经常项目。若金额 > NP 的 5% 且无法量化，标记 `data_gap: true` 和 `data_gap_note: "未在PDF中披露的FY20XX一次性收益，估计金额>XXM"`。
- 一旦 `data_gap: true` 涉及金额 > NP 的 5%，系统在 Zone J 中自动触发 g_base 下调 0.5%，confidence 降为 low。

**禁止提取**：营收/NP/OCF/Capex/毛利率/ROE/EPS/DPS——这些已在 data_pack_agent.md 中，且 compute_bundle 的精度远高于人工读 PDF。

### Step 2.3：输出 Zone B JSON

协调器将提取结果写入：
```
output/{DIR}/mda.json, segments.json, risks.json, governance.json, audit.json
```

完成后：
```bash
python3 scripts/boundary_validator.py --code {CODE} --boundary zone_b
```

## Phase 3：Zone J 参数估算（4 Agent 并行）

**前置条件**：Zone B 5 JSON 全部存在 + boundary_validator PASS。

对每个 agent ∈ ["moat","capex","earnings_quality","data_quality"]：

```bash
python3 scripts/zone_j_agent.py --code {CODE} --agent {agent} --save-prompt output/{DIR}/zone_j_prompt_{agent}.txt
```

协调器**并行调度 4 个 sub-agent**，每个读自己的 prompt 文件，按 schema 输出参数 JSON：

```
sub-agent: 你是 Zone J/{agent} 参数估算器。
  读 output/{DIR}/zone_j_prompt_{agent}.txt
  → 按其中的 JSON schema 输出参数
  → 每个参数格式: {value, rationale, evidence_ref, confidence}
  → 写入 output/{DIR}/{output_file}
```

**协调器检查**：每个 sub-agent 产出后验证 evidence_ref 非空。

4 个全部通过后：
```bash
# 1. Schema 校验
python3 scripts/boundary_validator.py --code {CODE} --boundary zone_j  # PASS

# 2. 精算：Zone J 参数注入 compute_bundle → compute_bundle_precise.json
python3 scripts/compute_bundle_precise.py --code {CODE}
# → GG/DDM/λ 使用 Zone J 精炼参数重新计算
# → 产出: compute_bundle_precise.json（覆盖默认 b_penalty/g_base/data_discount/mcapex_split）
# → 对比 base vs precise 差异，打印关键参数调整

# 3. 刷新数据包（含 precise 数据 + BS 字段）
python3 scripts/build_data_pack.py --code {CODE}
```

## Phase 4：Zone C 报告写作（V9.3: 单 Agent 模式）

**前置条件**：Zone B 5 JSON + Zone J 4 JSON + compute_bundle.json 全部存在。

```bash
# 生成 C_FULL prompt（合并 C1-C4，约 200K chars）
python3 scripts/zone_c_chain.py --code {CODE} --agent C_FULL --save-prompts --output output/{DIR}
```

协调器**调度 1 个 sub-agent**：

```
sub-agent-ZC: 读 zone_c_C_FULL_prompt.txt
  → 一次性写出完整报告（3000-4000 行）
  → 输出 zone_c_C_FULL_output.md
  → 即最终报告，无需拼接
```

**为什么是 1 个 Agent**：C1-C4 总上下文约 280K chars，1M 窗口完全容纳。单 Agent 确保因子间的计算一致性和定性定量交叉引用。

**回退**：如需调试单因子，仍可用 `--agent C1` 等生成分步 prompt。`--assemble` 自动检测 `C_FULL_output.md`，存在则直接使用。

## Phase 5：验证（强制）

组装完成后必须运行：

```bash
# 1. 质量门禁（强制，不通过则重装）
python3 scripts/quality_gate.py --code {CODE}
# 检查: 12 个必须章节、ES 非空、≥20 表格、≥1000 行、异常传播、DPS 口径

# 2. 引用验证
python3 scripts/citation_verifier.py --code {CODE}
```

**组装时的模板校验**：组装后自动检查报告是否包含旧框架 `<report_template>` 要求的 9 个必须章节。缺失章节打印 WARNING。

## 降级与异常处理

| 异常 | 处理 |
|------|------|
| page_map 章节缺失（某些 section 定位不到） | 协调器手动翻阅 PDF 目录页定位 |
| PDF 完全不可读（图片型扫描件） | 触发 tesseract OCR（`ocr_pdf_if_needed()` 自动处理） |
| PDF 文字层损坏（CJK 重复等） | `is_garbled()` 自动检测 → 标记 ⚠️ 跳过损坏页 |
| pdf_full_text 不存在 | Zone B 回退到旧 zone_b_extractor（单年 pdf_sections） |
| Zone B < 3 年可用 | 标注 ⚠️，汇总 Agent 只处理可用年份 |
| Zone J 输入缺失 | Agent 使用回落默认值（g_base=2.0%, b_penalty=0.25 等） |
| Zone C Agent 输出 < 目标 50% | 重新处理最多 1 次，仍不足→标注 ⚠️ 继续 |
| yfinance/Tushare 不可用 | 手动输入 price/shares，标注来源 |

## 硬约束

1. 协调器只调度 sub-agent，不亲自读 PDF 或处理 prompt
2. Zone B 并行（4 个年度 sub-agent）、Zone J 并行（4 个参数 sub-agent）、Zone C 顺序（6 个链式 sub-agent）
3. 每个 sub-agent 产出后协调器必须检查质量（行数、关键词、evidence_ref）
4. Zone C 禁止压缩表格——每个 [?] 必须替换
5. 所有 Zone 的降级必须标注 ⚠️
6. 不达标 → 重试 1 次，仍不达标 → 标注 ⚠️ 继续，不阻塞管道
7. **V9.3**: Zone B 必须穷举"其他收入/其他收益"附注，data_gap 涉及金额 > NP×5% 时标记
8. **V9.3**: Zone J 遇 data_gap 强制 g_base 下调 ≥0.5%，confidence → low
9. **V9.3**: C1 Executive Summary 必须包含悲观情景 DDM + 下行风险
10. **V9.3**: 报告完成前执行 `source_collector.py` + `quality_gate.py`
