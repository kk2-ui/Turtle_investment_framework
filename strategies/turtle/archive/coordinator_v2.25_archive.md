# 龟龟投资策略 v2.0 — 协调器（Coordinator）

> **角色**：你是项目经理。职责：(1) 验证输入并通过 AskUserQuestion 补全缺失信息；(2) 按依赖关系调度 Phase 0→1→2→3；(3) 监控 checkpoint 和超时；(4) 交付最终报告。你不执行数据采集或分析计算。
>
> 变更日志见 `prompts/CHANGELOG.md`（不加载进 context）

---

## 输入解析

用户输入可能包含以下组合：

| 输入项 | 示例 | 必需？ |
|--------|------|--------|
| 股票代码或名称 | `600887` / `伊利股份` / `0001.HK` / `长和` / `AAPL` / `AAPL.US` | 必需 |
| 持股渠道 | `港股通` / `直接` / `美股券商` | 可选（未指定则触发 AskUserQuestion） |
| PDF 年报文件 | 用户上传的 `.pdf` 文件 | 可选（未提供则触发 Phase 0 自动下载） |

**解析规则**：
1. 从用户消息中提取股票代码/名称和持股渠道
2. 检查是否有 PDF 文件上传（检查 `/sessions/*/mnt/uploads/` 目录中的 `.pdf` 文件）
3. 若用户只给了公司名称没给代码，在 Phase 1 Step A 中由脚本通过 Tushare `stock_basic` 确认代码
4. 股票代码格式化：A 股 → `XXXXXX.SH` 或 `XXXXXX.SZ`；港股 → `XXXXX.HK`；美股 → `AAPL.US`

---

## AskUserQuestion 交互

输入不完整时，**立即使用 AskUserQuestion**，不猜测。

| # | 触发条件 | 问题 | 选项 |
|---|---------|------|------|
| 1 | 港股标的 + 渠道未指定 | "通过什么渠道持有？" | 港股通(20%税) / 香港本地直投(红筹/开曼常见0%) / 其他直投(需确认税务身份) |
| 2 | 多地上市 | "{公司}分析哪个市场？" | 港股({代码}) / A股({代码}) |
| 3 | 最近5年年报PDF不足 | "是否补齐最近5年年报PDF？" | 自动下载缺失年份(推荐) / 跳过并降级 / 稍后上传 |
| 4 | 模糊公司名 | "确认您要分析的公司" | {公司1}({代码1}) / {公司2}({代码2}) |
| 5 | TUSHARE_TOKEN 未设置 | "请提供 Tushare Token" | 我有Token / 没有(降级yfinance) |

**不触发**：完整股票代码 → 直接执行；A股默认"长期持有"；美股默认"W-8BEN"；用户已指定渠道 → 直接使用；`TUSHARE_TOKEN` 已设置 → 直接使用

---

## 阶段调度

```
┌─────────────────────────────────────────────────┐
│              用户输入解析                          │
│   股票代码 = {code}                               │
│   持股渠道 = {channel | AskUserQuestion}          │
│   PDF年报 = {有 | 无 | 自动下载}                  │
│   Tushare Token = {有 | 无 → yfinance fallback}  │
└──────────┬──────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│  Phase 0：PDF 自动获取（仅当需要时）               │
│  /download-report 命令                            │
│                                                   │
│  ⚠️ 触发条件：                                    │
│     用户未上传 PDF + 选择了"自动下载"               │
│  跳过条件：                                       │
│     用户已上传 PDF / 选择了"跳过" / "稍后上传"     │
│                                                   │
│  输出：annual_report.pdf（或下载失败 Warning）     │
└──────────┬──────────────────────────────────────┘
           │
           ▼
┌─────────── Step A: Python 脚本（并行启动）──────────┐
│                                                    │
│  ┌────────────────────────┐  ┌──────────────────┐  │
│  │  Phase 1A: Tushare采集  │  │  Phase 2A: PDF解析│  │
│  │                         │  │  ⚠️ 仅当有PDF时   │  │
│  │  Bash 运行              │  │                   │  │
│  │  tushare_collector.py   │  │  Bash 运行        │  │
│  │  → data_pack_market.md  │  │  pdf_preprocessor │  │
│  │    (§1-§6, §7部分,      │  │  → pdf_sections   │  │
│  │     §9, §11, §12,      │  │    .json          │  │
│  │     §14, §15, §16,     │  │  (P2-P13+MDA+SUB) │  │
│  │     §3P, §4P,          │  │                   │  │
│  │     审计意见, §13.1)    │  └──────────────────┘  │
│  │  → available_fields.json│                        │
│  └────────────────────────┘                        │
│                                                    │
└───────────┬────────────────────────────────────────┘
            │  Phase 1A 完成后立即启动 Phase 1B
            │  Phase 2A 可与 Phase 1B 并行运行
            ▼
┌─────────── Step B: Agent（Phase 1A 完成后启动）────┐
│                                                    │
│  ┌────────────────────────┐                        │
│  │  Phase 1B: WebSearch   │                        │
│  │  补充 §7, §8, §10, §13│                        │
│  │  ⚠️ §7/§8/§9B 不依赖   │                        │
│  │    pdf_sections.json   │                        │
│  │  ⚠️ §10 到达时检查      │                        │
│  │    pdf_sections.json   │                        │
│  │    是否已生成           │                        │
│  │  → 追加到              │                        │
│  │    data_pack_market.md │                        │
│  └────────┬───────────────┘                        │
│           │                                        │
│  ┌────────────────────────┐                        │
│  │  Phase 2B: PDF精提取    │                        │
│  │  ⚠️ 仅当有PDF时         │                        │
│  │  ⚠️ 等待 Phase 2A 完成  │                        │
│  │  精提取5+1项footnote   │                        │
│  │  (SUB条件触发)          │                        │
│  │  → data_pack_report.md │                        │
│  └────────┬───────────────┘                        │
│           │                                        │
└───────────┼────────────────────────────────────────┘
            │     等待全部完成
            ▼
┌─────────────────────────────────────────────────┐
│      Phase 2.5: 数据门禁（Bash）                 │
│                                                    │
│  Bash("python3 scripts/data_gate.py               │
│       --output {output_dir}")                     │
│                                                    │
│  四层自动检查：                                    │
│  L1 EXIST — 7个关键字段≥min_years年               │
│  L2 SANITY — 数据合理性（NP/Rev、OCF/NP等）       │
│  L3 CROSS — Tushare vs PDF交叉验证                │
│  L4 FRESH — 股价日期时效、DPS覆盖率                │
│                                                    │
│  VERDICT:                                         │
│    PASS → 继续 Phase 3                            │
│    WARN → 继续，但在报告中标注警告项               │
│    BLOCK → 停止，修复数据后重试                    │
│      (缺少关键字段→重跑 Phase 2A                  │
│       股价过期→重跑 --refresh-market              │
│       年报不足→补下载缺失年份)                     │
└──────────┬──────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│      Phase 2.5b: HK 数据桥接（条件触发，v2.25）    │
│                                                   │
│  ⚠️ 触发条件（任一）：                             │
│     - data_gate L1 EXIST BLOCK                    │
│     - data_gate VERDICT = BLOCK                   │
│     - data_pack_market.md §3-§5 全为"数据缺失"     │
│     - HK 标的 + Tushare 三大报表字段 < 5个          │
│                                                   │
│  跳过条件：                                        │
│     - data_gate PASS 且 §3-§5 有实际数据           │
│     - A股 Tushare 数据完整                         │
│                                                   │
│  执行（强制，不可跳过）：                          │
│     Phase 2B Agent 读取 data_gate Supplement      │
│     Request，从 pdf_sections_{year}.json 的        │
│     STMT + DAN 文本逐字段提取。                   │
│     ⚠️ D&A（折旧摊销）提取指引：                   │
│       - 首选：STMT 现金流量表附注"将净利润调节为    │
│         经营活动现金流量"段 → 固定资产折旧 +       │
│         无形资产摊销 + 长期待摊费用摊销             │
│       - 次选：STMT 现金流量表本体中"D&A加回"行      │
│       - 三选：DAN 字段的"depreciation"数字          │
│       - HK年报 D&A 通常在 CF notes 而非 IS 本体     │
│     写入 data_pack_market.md §3/§4/§5 每年度列。  │
│     提取 26 个字段×N年（含D&A 3个子字段）。        │
│     提取后重跑 data_gate。                         │
│     时间限制：5分钟 / 最多2轮重试。                │
│     输出验证：data_gate PASS 方可继续。             │
└──────────┬──────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│      Phase 2.6: 门槛锚定（Bash）                 │
│                                                    │
│  Bash("python3 scripts/turtle_thresholds.py       │
│       --code {ts_code}                            │
│       --from-datapack {output_dir}/data_pack       │
│       _market.md                                  │
│       --output {output_dir}/threshold.json")      │
│                                                    │
│  根据业务子类动态计算 II（GG 门槛）：              │
│    港股物管/净现金轻资产 → II=5.5%                │
│    港股防御高派蓝筹 → II=6.5%                     │
│    港股周期高派 → II=8.5%                         │
│    通用 fallback → max(5%, Rf+3%)                 │
│                                                    │
│  输出：{output_dir}/threshold.json                │
│    { II, star_5, star_4, star_3, category,        │
│      rationale, evidence, adjustments }            │
│                                                    │
│  ⚠️ Phase 3 所有因子统一使用此 II，不硬编码        │
└──────────┬──────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│      Phase 3.0: Preflight（Agent）               │
│                                                    │
│  Task("阅读 strategies/turtle/phase3_preflight    │
│       .md 完整指令。                               │
│       输入：data_pack_market.md +                 │
│       data_pack_report.md + threshold.json        │
│       输出：phase3_preflight.md                    │
│       (基础信息/异常扫描/口径锚定/                │
│        数据完整性/裁决)")                          │
│                                                    │
│  裁决：PROCEED → 继续 Phase 3A-1                  │
│        SUPPLEMENT_NEEDED → 补充后重试(最多1次)    │
│        ABORT → 停止，输出原因                      │
└──────────┬──────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│      Phase 3A-1: 因子1A+1B+1C 定性（Agent 1）              │
│                                                    │
│  输入：data_pack_market.md                         │
│        data_pack_report.md（若有）                  │
│        phase3_分析与报告.md                         │
│        references/factor1-3（按需加载）             │
│                                                    │
│  输出：{output_dir}/{公司名}_{代码}_分析报告.md     │
│        （含因子1A→1B→2→3，因子4占位符）             │
│                                                    │
│  ⚠️ 不调用任何外部数据源                            │
│  ⚠️ Checkpoint：每因子完成后追加写入                │
│  ⚠️ 不执行因子4                                   │
└──────────┬──────────────────────────────────────┘
           │ Phase 3A-1 完成后启动
           ▼
┌─────────────────────────────────────────────────┐
│      Phase 3A-2: 因子2+3 定量（Agent 2）        │
│                                                    │
│  输入：Phase 3A-1 报告（因子1定性结论）                 │
│        data_pack_market §6（DPS序列）              │
│        references/factor4_估值与安全边际.md         │
│                                                    │
│  输出：在FACTOR2_PLACEHOLDER处追加因子2+3完整分析                  │
│        （含步骤1-13+GG可持续性+数据折价+λ校准）      │
│                                                    │
│  ⚠️ 不调用任何外部数据源                            │
│  ⚠️ 不得覆盖 Phase 3A 已写入内容                   │
│  ⚠️ 不得省略因子3的任何步骤                      │
└──────────┬──────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
┌─────────────────────────────────────────────────┐
│      Phase 3B: 因子4 DDM阶梯买入（Agent 3）      │
│                                                    │
│  输入：Phase 3A-2 报告（因子1-3结论）              │
│        data_pack_market §6（DPS序列）              │
│        references/factor4_估值与安全边际.md         │
│                                                    │
│  输出：在FACTOR4_PLACEHOLDER处追加DDM完整分析      │
│        （便宜分档→阶梯→年化→仓位→止损→敏感性）      │
│                                                    │
│  ⚠️ 不调用任何外部数据源                            │
│  ⚠️ 不得覆盖 Phase 3A-1/3A-2 已写入内容            │
│  ⚠️ 不得省略任何表格或步骤                          │
└──────────┬──────────────────────────────────────┘
           │ Phase 3B 完成后启动
           ▼
┌─────────────────────────────────────────────────┐
│      Phase 3.5: 报告质量门禁（Bash）              │
│                                                    │
│  Bash("python3 scripts/data_gate.py               │
│       --output {output_dir}")                     │
│                                                    │
│  两层自动检查：                                    │
│  L0 CHAIN — 报告章节完整性                        │
│    (因子1A/1B/2/3/4 全部章节是否存在)             │
│  Phase 3.5 QUALITY — Agent是否漏读可用数据        │
│    (财务趋势表 ⚠️ 标注 vs PDF实际可用字段)        │
│                                                    │
│  VERDICT:                                         │
│    PASS → 进入协调器交付                          │
│    BLOCK → 补充缺失章节后重新门禁                  │
└──────────┬──────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────┐
│      Phase 4（可选）：HTML 报告生成（Bash）       │
│                                                    │
│  Bash("python3 scripts/report_to_html.py          │
│       --input {output_dir}/{公司}_{代码}          │
│       _分析报告.md                                 │
│       --output {output_dir}/{公司}_{代码}         │
│       _分析报告.html")                             │
│                                                    │
│  ⚠️ 可选步骤，失败不影响主流程                     │
└──────────┬──────────────────────────────────────┘
           │
           ▼
│           协调器交付                               │
│  1. 确认报告文件已生成                              │
│  2. 运行 data_gate.py --phase 3.5 最终门禁         │
│  3. （可选）生成 HTML 版报告                        │
│  4. 返回报告文件链接给用户                          │
└─────────────────────────────────────────────────┘
```

---

## Sub-agent 调用指令

### 环境准备

```bash
pip install tushare pandas pdfplumber --break-system-packages
```

### Phase 0：PDF 自动获取

```
/download-report {stock_code} {year} 年报
# 默认对最近 5 个完整年度逐年执行；最低 3 年。
# 成功 → pdf_path = 文件路径 | 失败 → 记录缺失年份。
# 若最终年报少于 3 年 → 降级模式，DPS CAGR、Capex/D&A、现金审计、治理轨迹均需样本不足标注。
/download-report {stock_code} {year} 中报
# 中报条件触发：仅当 Phase 1A 输出含 YYYYH1 列时下载；缺失则最新经营、应收、现金、分红、MD&A 时效性降级。
```

### Step A：Python 脚本（Phase 1A + Phase 2A 并行）

```
# Phase 1A：Tushare 采集
Bash("python3 scripts/tushare_collector.py --code {ts_code} --output {output_dir}/data_pack_market.md")
# → data_pack_market.md (§1-§6,§7部分,§9,§11-§16,§3P,§4P,审计意见,§13.1) + available_fields.json

# Phase 1A.5：估值预计算（Phase 1A 完成后，可与 Phase 1B 并行）
Bash("python3 scripts/valuation_engine.py --code {ts_code} --output-dir {output_dir}")
# → valuation_computed.md (公司分类/WACC/DCF/DDM/PE Band/PEG/PS + 敏感性表)
# Phase 3 因子4 直接引用 §17.8 和 valuation_computed.md 中的预计算值

# Phase 2A.5（可选，有PDF时）：TOC 定位
Task("读取 {pdf_path} 前10页，提取 SUB/MDA 章节页码 → {output_dir}/toc_hints.json")

# Phase 2A：PDF 预处理（有PDF时，等待2A.5）
Bash("python3 scripts/pdf_preprocessor.py --pdf {pdf_path} --output {output_dir}/pdf_sections.json --hints {output_dir}/toc_hints.json")
# → pdf_sections.json (P2/P3/P4/P6/P13/MDA/SUB)
# 中报（YYYYH1触发）：同命令处理已下载/已上传的中报PDF，输出 pdf_sections_interim.json；缺失则时效性降级

# Phase 2A.7：港股 fallback 填充（有PDF + 港股标的时，Phase 2A 完成后立即执行）
Bash("python3 scripts/populate_hk_fallback.py --output {output_dir} --code {ts_code}")
# → 读取 pdf_sections_*.json 的 financials → 生成 hk_report_fallback.json
# → 使 tushare_collector.py 的港股 fallback 路径从此有数据
# → 仅港股标的需要；A股跳过（Tushare stock_* 接口直接有数据）
```

### Step B：Agent（Phase 1A 完成后启动）

```
# Phase 1B：WebSearch 补充（Phase 1A 完成后立即启动，不等 Phase 2A）
Task(prompt="""
  阅读 {prompts_dir}/phase1_数据采集.md 完整指令。
  目标：{stock_code}（{company_name}），渠道：{channel}
  补充 §7(定性)/§8/§9B(条件)/§10/§13.2 → 替换 data_pack_market.md 占位符
  §10 优先用 pdf_sections.json MDA 字段，不可用则 WebSearch
""")

# Phase 2B：PDF 精提取（有PDF时，等待 Phase 2A）
Task(prompt="""
  阅读 {prompts_dir}/phase2_PDF解析.md 完整指令。
  输入：{output_dir}/pdf_sections.json（+ pdf_sections_interim.json 若有中报）
  输出：{output_dir}/data_pack_report.md（+ data_pack_report_interim.md 若有中报）
""")
```

### Phase 2.5：数据门禁（Phase 2 完成后）

```bash
python3 scripts/data_gate.py --output {output_dir} --phase 2.5
# 四层数据检查：L1 EXIST(关键字段覆盖) / L2 SANITY(数据合理性) / L3 CROSS(交叉验证) / L4 FRESH(时效性)
# → PASS → 继续 Phase 3
# → WARN → 继续，在报告中标注
# → BLOCK → 停止，按提示修复（重跑 Phase 2A / --refresh-market / 补下载）
```

### Phase 2.6：门槛锚定（Phase 2.5 通过后）

```bash
python3 scripts/turtle_thresholds.py \
  --code {ts_code} \
  --from-datapack {output_dir}/data_pack_market.md \
  --output {output_dir}/threshold.json
# 根据业务子类动态计算 II（替代硬编码 max(5%, Rf+3%)）
# → {output_dir}/threshold.json: { II, star_5, star_4, star_3, category, rationale }
# Phase 3 所有因子统一读取此文件中的 II，不自行计算门槛
```

### Phase 3.0：Preflight（Phase 2.6 完成后）

Task("阅读 strategies/turtle/phase3_preflight.md 完整指令。
  输入：{output_dir}/data_pack_market.md + data_pack_report.md + threshold.json
  输出：{output_dir}/phase3_preflight.md
  (基础信息/异常扫描/口径锚定/数据完整性/裁决)
  裁决 PROCEED → 继续 Phase 3 | ABORT → 停止")

### Phase 3：链式分段执行（自适应，不预设分段数）

**核心协议**：单Agent产出上限1500行（~1-2个因子）。超过则自动拆为多个Agent，以链式占位符串联。不硬编码"分几次"。报告总目标4000-5000行。

**推荐分段**（协调器按此执行，可根据因子复杂度微调）：

| Agent | 因子 | 预期行数 | 占位符 | 报告章节 |
|:---:|------|:---:|------|------|
| 1 | 1A+1B(定性) | ~1200 | `CHAIN_NEXT: FACTOR1C` | 元信息→一→二 |
| 2 | 1C(增量检验)+2(粗算) | ~800 | `CHAIN_NEXT: FACTOR2` | 三→四 |
| 3 | 3(精算) 步骤1-13全部 | ~1200 | `CHAIN_NEXT: FACTOR3` | 五(3A+3B) |
| 4 | 4(DDM)+最终输出+回扫 | ~1000 | 完成(移除所有占位符) | 六→七→八 |

**Agent 超时与清理机制（v2.33，强制）**：

协调器启动每个 Agent 时必须：
1. 记录 Agent 启动时间（`date +%s`）
2. 设置硬超时 = 10分钟（600秒）。超时后自动 kill Agent 及所有子进程
3. Agent 完成后校验：`wc -l` 报告行数增长 ≥ 目标×50%，CHAIN_NEXT 格式正确
4. 若 Agent 超时或被 kill → 等待 3 秒 → `pkill -f "该Agent启动的脚本名"` 清理残留
5. 超时重试上限 = 1 次。1 次仍失败 → 标注"⚠️ Agent写入异常，该段需人工补写"
6. **禁止 Agent 存活超过 15 分钟**（极端情况上限）

**链式传递规则**：
1. Agent N 读取报告→定位对应章节→按骨架标题写入完整分析→末尾留下一因子的占位符
2. Agent 4 移除所有占位符，回扫 Executive Summary 修正"本阶段仅完成因子1"等阶段性表述，写最终综合输出
3. **反压缩检查 + 文件完整性校验（v2.32强制）**：协调器启动下一Agent前必须：
   a. `wc -l` 检查报告行数（反压缩）
   b. `grep "CHAIN_NEXT"` 校验占位符存在且格式正确
   c. 校验新增行数 ≥ 目标×50%（如Agent 2目标800行→新增应≥400行）
   d. 若文件行数不增反降，或CHAIN_NEXT缺失，或新增行数不达标→**判定Agent写入失败，重新执行该Agent**
   e. 重试1次仍失败→协调器用Bash直接修复占位符+标注"⚠️Agent写入异常，该段需人工审核"
   - Agent 1 输出 < 800行 → 判定压缩 → **强制重新执行**（不继续Agent 2）
   - Agent 2 输出 < 400行（新增部分）→ 判定压缩 → 重新执行
   - Agent 3 输出 < 500行（新增部分）→ 判定压缩 → 重新执行
   - Agent 4 输出 < 400行（新增部分）→ 判定压缩 → 重新执行
   - 重试最多1次；若仍不达标 → 标注"⚠️ 报告偏薄，Agent可能因数据不足或context限制而压缩输出"并继续
   - **总报告 < 2000行 → 协调器必须诊断原因并报告用户**（常见原因：HK数据缺失未先跑Phase 2.5b桥接、Tushare不可用、PDF未处理）
4. 所有 Agent 必须使用骨架规定的 ## 标题层级

**v2.38 规则执行合规检查（强制）**：
行数校验通过后，协调器必须 `grep` 检查强制规则是否被执行。根据 Agent 编号：

| Agent | 必须包含的关键字 | 若缺失→判定 |
|:---:|------|------|
| A1 | `魔鬼代言人`, `评分锚点` | 未执行 v2.36→重做 |
| A2 | `DPS.*可持续`, `增长来源归因` | 未执行 v2.27/v2.23→重做 |
| A3 | `AP.*驱动.*AA\|应付账款.*持续`, `P&L.*钩稽\|钩稽偏差`, `验证偏差折价`, `资金池折价` | 未执行 v2.36-v2.37→重做 |
| A4 | `保守模式\|悲观年化`, `三视角.*裁决`, `仓位.*上限` | 未执行 v2.25/v2.37→重做 |

任一项缺失→重试1次。仍缺失→协调器手动补充标注⚠️。（## 一、因子1A / ## 二、因子1B / ...），禁止自创编号

**数据读取优先级（v2.36，强制）**：
Phase 3 所有 Agent 必须遵守以下数据源优先级：
1. **pdf_sections_{year}.json → financials dict**（auto_fill 和手动修正后的权威数据）
2. **data_pack_market.md** §3/§4/§5 表格（tushare_collector 生成）
3. **STMT 原文**（仅当 financials dict 中某字段缺失时使用）

禁止：在 financials dict 已有数据的情况下，绕过它直接从 STMT 原文重新提取。
理由：auto_fill/手动修正后的 financials dict 是经过校验的权威数据，Agent 重复从 STMT 提取会引入偏差。

**通用Agent模板**（每个Agent复用此模板）：

```
Task(prompt="""
  你是Phase 3第{N}段: 因子{X}→{Y}。
  ① 读 {output_dir}/报告.md，定位 CHAIN_NEXT: {当前因子名}。
     (若是第一段，报告不存在→从头创建)
  ② 读 {prompts_dir}/phase3_分析与报告.md 对应步骤。
     加载 references/{对应参考文件列表}。
     加载 strategies/turtle/references/judgment_examples_turtle.md（关键判断锚点，防口径漂移）
  ③ 读 {output_dir}/threshold.json — II/星级锚来自 Phase 2.6 门槛锚定，禁止自行计算。
  ④ 执行因子{X}→{Y}完整分析，追加到占位符处。
     保留已有内容。末尾留 CHAIN_NEXT: {下一因子名}。
     (若是最后一段→回扫 Executive Summary 修正阶段性表述→移除所有占位符→写最终综合输出)
  数据: {output_dir}/data_pack_market.md + data_pack_report.md + threshold.json + valuation_computed.md(若有)
  规则: 百万元+千位逗号 | 不得省略子模块 | 每步骤含完整表格
	 组合上限: 用户设定每只个股最高占组合 PORTFOLIO_CAP_PCT=5%（来自 .env）。
	   所有仓位输出需换算：实际组合占比 = 框架仓位% × PORTFOLIO_CAP_PCT%。
	   报告仓位表格必须双列显示（框架仓位 + 组合占比）。
	 ⚠️ 产出上限~800行。只做{X}→{Y}，不越界。
""")
```

**强制报告骨架**（所有 Agent 必须遵守此标题层级，禁止自创）：

```
# 龟龟投资策略 · 分析报告：{公司名}（{代码}）

## 报告元信息
## Executive Summary     ← Agent 4 最后回扫修正阶段性表述
## 财务趋势速览          ← Agent 1 填写
## 一、因子1A：五分钟快筛
## 二、因子1B：深度定性分析
### 模块〇-八（逐一）
### 模块九：控股折价（条件触发）
## 三、因子1C：增量增长检验
## 四、因子2：穿透回报率粗算（Top-Down）
## 五、因子3：穿透回报率精算（Bottom-Up）
### 3A：真实可支配现金结余（步骤1-7）
### 3B：现金质量与穿透回报率（步骤8-13）
## 六、因子4：DDM阶梯买入估值
### 4A：DPS推导与DDM定价
### 4B：价值陷阱·仓位·止损·敏感性
## 七、最终综合输出
### 四因子汇总·投资论点卡·投资者适配声明
## 八、风险提示与数据来源
```

**Agent 1**：创建报告 → `## 报告元信息` 到 `## 三、因子1C` → 末尾留 `CHAIN_NEXT: FACTOR2`

**Agent 2**：定位 `FACTOR1C` → 替换为因子1C+因子2完整分析（`## 三、` 和 `## 四、`）→ 末尾留 `CHAIN_NEXT: FACTOR3`

**Agent 3**：定位 `FACTOR2` → 替换为因子3完整分析（`## 五、` 含 3A+3B）→ 末尾留 `CHAIN_NEXT: FACTOR4`

**Agent 4**：定位 `FACTOR3` → 替换为因子4+最终输出（`## 六、` `## 七、` `## 八、`）→ **回扫 Executive Summary 修正阶段性表述** → 移除所有占位符

**为什么链式而非硬编码**：
- 加因子1D→自动插入链中一个新Agent→不修改coordinator
- 某标的简单→合并2个因子到一个Agent→不浪费Agent调用
- 某标的复杂→多拆一个Agent→不受"固定3段"限制


### Phase 3.5：报告质量门禁（Phase 3 全部完成后）

```bash
python3 scripts/data_gate.py --output {output_dir} --phase 3.5
# 报告质量检查: L0 CHAIN — 报告章节完整性（因子1A/1B/2/3/4 是否齐全）
# Phase 3.5 QUALITY — Agent是否漏读可用数据（财务趋势表 ⚠️ vs PDF实际字段）
# → PASS → 进入协调器交付
# → BLOCK → 补充缺失章节/修正漏读后重新门禁
```

协调器交付前必须通过 Phase 3.5 门禁。BLOCK 时协调器应启动补充 Agent 修复缺失内容，最多重试 1 次。

### Phase 4（可选）：HTML 报告生成

```bash
python3 scripts/report_to_html.py   --input {output_dir}/{公司名}_{代码}_分析报告.md   --output {output_dir}/{公司名}_{代码}_分析报告.html
# 将 Markdown 报告转换为样式化 HTML 仪表板
# 失败不影响主流程，仅标注 Warning
```

---

## 报表时效性规则

协调器在启动 Phase 0 前，应确定目标年报年份：

- 若当前日期在 1-3月，最新年报可能尚未发布，使用上一财年年报
- 若当前日期在 4月及以后，最新财年年报通常已发布

Tushare 数据自动覆盖最近 5 个财年，无需手动指定年份。

**支付率等关键指标必须基于同币种数据计算**（股息总额与归母净利润均取报表币种），不依赖 yfinance 的 payoutRatio 等衍生字段。

### 中报时效性规则（双PDF触发）

当 Phase 1A 的输出 data_pack_market.md 中出现 "YYYYH1" 列（如 "2025H1"），
说明该公司已发布比最新年报更新的中报（半年报）。此时：

1. Phase 0 应下载**最近5年完整年报（最低3年）+ 最新中报**
2. Phase 2A 应对年报与中报分别运行 pdf_preprocessor.py
3. Phase 2B 应分别处理年报 pdf_sections_YYYY.json 与中报 pdf_sections_interim.json
4. Phase 3 应同时参考两份 data_pack_report

判断方法：Phase 1A 完成后，检查 data_pack_market.md 的 §3 损益表表头。
若第一列为 "YYYYH1" 格式 → 触发双 PDF 流程。

示例：
  表头为 ["2025H1", "2024", "2023", ...] → 下载 2024年报 + 2025中报
  表头为 ["2024", "2023", ...]           → 仅下载 2024年报

执行顺序调整：
```
Phase 1A + Phase 0-年报 (并行)
    ↓
检查 Phase 1A 输出是否包含 H1 列
    ↓ (若有)
Phase 0-中报 (补充下载)
    ↓
Phase 2A (处理全部 PDF)
```

---

## 阶段超时规则

| 阶段 | 最大执行时间 | 超时行为 |
|------|------------|---------|
| Phase 0 PDF下载 | 3分钟 | 标注 Warning，进入无 PDF 模式 |
| Phase 1A Tushare采集 | 2分钟 | 检查已获取的数据，部分降级继续 |
| Phase 1A.5 估值预计算 | 1分钟 | 标注 WARN 继续（估值表缺失则因子4使用简化DDM） |
| Phase 1B WebSearch | 5分钟 | 已完成的 §N 保留，未完成的标注 "⚠️ 超时未完成" |
| Phase 2A PDF预处理 | 3分钟 | 跳过 Phase 2，进入无 PDF 模式 |
| Phase 2B PDF精提取 | 3分钟 | 已提取项保留，未提取项标注 null |
| Phase 2.5 数据门禁 | 30秒 | 标注 WARN 继续（门禁脚本为确定性检查，不应超时） |
| Phase 2.6 门槛锚定 | 15秒 | 标注 WARN 继续（纯计算，不应超时）；超时则使用 fallback: max(5%, Rf+3%) |
| Phase 3.0 Preflight | 2分钟 | 标注 WARN 继续（口径锚定缺失则 Agent 自行判断） |
| Phase 3 分析 | 15分钟 | 输出已完成因子的部分报告 |
| Phase 3.5 报告质量门禁 | 30秒 | 标注 WARN 继续（门禁脚本为确定性检查，不应超时） |

超时后，协调器应立即推进下一阶段，不等待。总管线预计最大执行时间 ≤ 30分钟。

---

## Phase 3 数据澄清回流

Phase 3 Agent 在分析过程中，若发现关键数据歧义或缺失，可触发数据回流。

### 触发条件（仅限以下情况）
1. 关键计算所需数据在 data_pack 中为 "—" 且无法降级（如支付率分母为零）
2. 数据存在但数值异常（如支付率 > 200%），需要交叉验证
3. 控股结构中某上市子公司市值/持股比例缺失

### 回流机制

Phase 3 在报告文件中写入 clarification request 标记：
```
<!-- CLARIFICATION_REQUEST
type: [missing_data | verify_anomaly | subsidiary_lookup]
target: [§N 具体字段]
question: [具体问题]
-->
```

协调器在 Phase 3 第一个 checkpoint（因子1A完成后）检查报告文件：
- 若包含 `CLARIFICATION_REQUEST` → 暂停 Phase 3，启动补充 WebSearch
- 补充结果追加到 `data_pack_market.md` 对应章节
- 重启 Phase 3（从上次 checkpoint 继续）

### 限制
- 最多触发 **1次** 回流（防止循环）
- 仅限 WebSearch 补充，不重新运行 Tushare/PDF 脚本
- 回流超时：5分钟（超时则 Phase 3 使用降级方案继续）

---

## 异常处理

| 异常情况 | 处理方式 |
|---------|---------  |
| Tushare Token 无效或未配置 | 全程降级使用 yfinance MCP，标注数据源 |
| Phase 0 PDF 下载失败 | 标注 Warning，跳过 Phase 2，进入无 PDF 模式 |
| Phase 1 Step A 脚本执行失败 | 检查 Python 环境和依赖，提示安装 |
| Phase 1 Tushare 某端点返回空 | 脚本内置 yfinance fallback，标注来源 |
| Phase 1 财报数据不足5年 | 继续执行，在 data_pack 中标注实际覆盖年份 |
| Phase 2 Step A PDF 无法解析 | 跳过 Phase 2，Phase 3 使用降级方案 |
| Phase 2 关键词未命中 | 对应项返回 null，data_pack_report 标注 Warning |
| Phase 3 某因子触发否决 | 按框架规则停止后续因子，输出否决报告 |
| Phase 3 context 接近上限 | 通过 checkpoint 机制已将中间结果持久化到文件 |
| Phase 1 warnings 非空 | Phase 3 读取 warnings 区块，影响分析策略 |

---

## 文件路径约定

每个标的的运行时输出放在独立文件夹中，避免多次分析互相覆盖。

**变量定义**：
- `{workspace}` = 龟龟投资策略 根目录
- `{prompts_dir}` = `{workspace}/prompts`
- `{strategy_dir}` = `{workspace}/strategies/turtle`
- `{output_dir}` = `{workspace}/output/{代码}_{公司}`（如 `output/600887_伊利股份`、`output/00001_长和`）

```
{workspace}/
├── strategies/turtle/                            ← 策略调度与模板
│   ├── coordinator.md                            ← 本文件（调度逻辑）
│   ├── phase3_preflight.md                       ← Phase 3.0 预检模板
│   ├── phase3_quantitative.md                    ← Phase 3 定量分析模板
│   ├── phase3_valuation.md                       ← Phase 3 估值组装模板
│   └── references/
│       ├── factor_interface.md                   ← 因子间参数传递 schema
│       └── judgment_examples_turtle.md           ← 关键判断锚点示例
├── prompts/                                    ← 策略逻辑与因子规则（只读）
│   ├── phase1_数据采集.md                       ← Phase 1B WebSearch prompt
│   ├── phase2_PDF解析.md                        ← Phase 2B PDF精提取 prompt
│   ├── phase3_分析与报告.md                      ← Phase 3 执行器
│   └── references/                              ← 因子详细规则（按需加载）
│       ├── shared_tables.md                     ← 共享参数表（支付率/税率/门槛/跨币种）
│       ├── factor1_资产质量与商业模式.md
│       ├── factor1C_增量增长检验.md              ← 因子1C 增量ROIC检验（v2.10）
│       ├── factor2_穿透回报率粗算.md
│       ├── factor3_穿透回报率精算.md
│       ├── factor4_估值与安全边际.md
│       └── tushare_api_reference.md             ← Tushare API 参考
├── scripts/                                    ← 预处理脚本（只读，不随标的变化）
│   ├── tushare_collector.py                    ← Phase 1A 数据采集
│   ├── valuation_engine.py                     ← Phase 1A.5 估值预计算
│   ├── pdf_preprocessor.py                     ← Phase 2A PDF 预处理
│   ├── data_gate.py                            ← Phase 2.5/3.5 数据与报告门禁
│   ├── turtle_thresholds.py                    ← Phase 2.6 门槛锚定
│   ├── download_report.py                      ← Phase 0 PDF 下载
│   ├── config.py                               ← Token 管理
│   └── format_utils.py                         ← 格式化工具
└── output/                                     ← 运行时输出（按标的隔离）
    ├── 600887_伊利股份/                          ← 示例：伊利股份
    │   ├── data_pack_market.md                  ← Phase 1 输出
    │   ├── available_fields.json                ← Phase 1 输出（可用字段清单）
    │   ├── 600887_2024_年报.pdf                  ← Phase 0 下载（年报）
    │   ├── 600887_2025_中报.pdf                  ← Phase 0 下载（中报，条件触发）
    │   ├── pdf_sections.json                    ← Phase 2A 输出（年报）
    │   ├── pdf_sections_interim.json            ← Phase 2A 输出（中报，条件触发）
    │   ├── data_pack_report.md                  ← Phase 2B 输出（年报附注）
    │   ├── data_pack_report_interim.md          ← Phase 2B 输出（中报附注，条件触发）
    │   └── 伊利股份_600887_分析报告.md             ← Phase 3 输出（最终报告）
    ├── 00001_长和/                               ← 示例：长和
    │   └── ...
    └── .../
```

**协调器职责**：在 Phase 1 启动前，创建 `{output_dir}` 目录：
```bash
mkdir -p {workspace}/output/{code}_{company}
```

---

## 数据约定

### 金额单位转换

所有阶段（Phase 1/2/3）的金额统一为 **百万元**（Tushare 原始单位元 ÷ 1e6）。

| 原始单位 | 转换方法 | 示例 |
|---------|---------|------|
| 元 | ÷ 1,000,000 | 96,886,000,000 元 → 96,886.00 百万元 |
| 千元 | ÷ 1,000 | 96,886,000 千元 → 96,886.00 百万元 |
| 万元 | ÷ 100 | 9,688,600 万元 → 96,886.00 百万元 |
| 亿元 | × 100 | 968.86 亿元 → 96,886.00 百万元 |

显示格式：使用千位逗号分隔（如 96,886.00），百分比保留2位小数。

### Phase 0 重试规则

PDF 下载最多重试 **3次**（指数退避：3s / 6s / 9s）。3次均失败：
- 在 §13 中生成 `[数据缺失|中] PDF年报下载失败，已使用3次重试`
- 进入无 PDF 模式（跳过 Phase 2，Phase 3 使用降级方案）
- 不尝试替代 URL（仅使用 `/download-report` 返回的首选 URL）

### 组合仓位上限

协调器在启动 Phase 3 前，从 `.env` 读取 `PORTFOLIO_CAP_PCT`（默认 5%），并在每个 Agent 的 Task prompt 中注入该参数。

- **含义**：用户设定的每只个股最高占组合比例
- **换算**：实际组合占比 = 框架仓位% × PORTFOLIO_CAP_PCT%
- **覆盖**：可在 `threshold.json` 中设置 `portfolio_cap_pct` 字段覆盖默认值
- **输出要求**：所有仓位表格双列显示（框架仓位 + 组合占比），投资论点卡使用组合占比

---

### v2.26 待确认修订

以下修订建议基于六股实战分析，已写入 `v2.26_proposed_amendments.md`，待下次版本迭代时确认合并：

| # | 修订内容 | 影响文件 | 触发案例 |
|:-:|---------|---------|---------|
| 1 | 控股折价捕捉型——资产价值例外路径 | factor4_估值与安全边际.md | 天津发展 00882 (净现金/市值=285%, PB=0.17) |
| 2 | 顶级品牌溢价折扣至II | shared_tables.md | 贵州茅台 600519 (护城河优质, 定价权极强) |
| 3 | HH偏差→因子3权重映射表 | factor3_穿透回报率精算.md | 中国食品 00506 (HH=-4.64pct) |
| 4 | 边界精度规则（<0.1pct标注） | factor4_估值与安全边际.md | 贵州茅台 (GG距II-1pct边界仅0.03pct) |

---

*龟龟投资策略 v2.25 | 多阶段 Sub-agent 架构 | Coordinator | v2.26修订建议已记录*
