# 龟龟投资策略 · V5.3 协调器设计方案

> 本文件是设计规格，不是实现代码。目标：写出新版协调器的完整 markdown 文件。

---

## 0. 当前协调器诊断：为什么不够用

### 0.1 现状（run_pipeline.py）

| 问题 | 具体表现 | 影响 |
|------|---------|------|
| **LLM步骤全是"手动"** | Step 3/6/10标注"手动"，pipeline只生成prompt，告知用户"自己处理" | 没有自动化，没有质量反馈循环 |
| **无报告组装逻辑** | C1/C2/C3/C4四个输出文件各自独立，pipeline不组装成最终报告 | 报告从未真正"生成" |
| **无行数校验/反压缩** | 只有最低行数检查（C1≥400行），不通过直接FAIL，无重试 | 短输出会卡住整个流程 |
| **无质量门禁** | 无旧版Phase 2.5/Phase 3.5的章节完整性检查 | 报告可能缺失整个因子章节 |
| **无AskUserQuestion** | 不询问持股渠道、不确认多地上市 | Q税率错误、货币单位混乱 |
| **无重试机制** | 任何步骤失败直接STOP | 一次API超时就需要手动干预 |
| **无超时控制** | LLM步骤无时间限制 | 长时间挂起无处理方案 |
| **状态机被文件欺骗** | 用文件是否存在判断完成——旧文件存在即跳过 | 修改prompt后需手动删除文件重置 |

### 0.2 旧版协调器（coordinator.md v2.25）的优点

旧版是专为Claude对话设计的指令文件，Claude作为协调器直接执行：

| 机制 | 旧版实现 | 效果 |
|------|---------|------|
| AskUserQuestion | Phase 0: 5个触发条件（渠道/多地上市/PDF/Tushare/模糊名称） | 参数完整再开始 |
| 并行启动 | Phase 1A + 2A 并行（Bash后台） | 节省等待时间 |
| CHAIN_NEXT链式传递 | Agent写完写占位符，下个Agent定位并接续 | 单文件渐进写入，上下文连续 |
| 反压缩检查（v2.32） | 每个Agent完成后wc -l，行数增长<目标×50%→重做 | 防止Agent输出过短 |
| 超时机制（v2.33） | 每Agent 10分钟硬超时，pkill清理子进程 | 不会永久挂起 |
| Phase 2.5 数据门禁 | data_gate.py L1-L4检查，BLOCK则暂停修复 | 数据不完整不进入报告 |
| Phase 3.5 报告质量门 | 检查因子章节完整性 + Agent是否漏读数据 | 报告不缺章节 |
| Executive Summary回扫 | Agent4最后回扫修正阶段性表述 | ES内容与报告一致 |
| 数据澄清回流 | CLARIFICATION_REQUEST标记，协调器补充数据 | Agent运行中可补数据 |
| 分段容量管理 | 每Agent目标行数，按复杂度自适应拆分 | 不会超出context限制 |

---

## 1. V5.3 协调器设计原则

### 1.1 双轨制：Python处理确定性，Claude处理判断性

```
Python (自动化，无LLM)          Claude (对话协调器)
─────────────────────          ──────────────────────────────
Zone A：compute_bundle          Phase 0：输入解析 + AskUserQuestion
Zone A：financial_trends        Phase 3：Zone C 4-Agent写作链
Zone B：提取prompts生成         Phase 3.5：报告质量门禁
Zone J：判断prompts生成         Phase 4：Executive Summary回扫
交叉验证、数据门禁               错误恢复、重试决策
规则引擎
报告验证（citation_verifier）
```

### 1.2 单文件渐进写入 + 结构化 handoff

`CHAIN_NEXT` 保留为拼接/人工流程标记，但不再承担唯一上下文传递职责。C1/C2/C3/C4 之间必须通过 `chain_context.json` 传递关键结论、参数锚点和待回扫事项。

```
Agent C1 → 写 报告头部+1A+1B → 更新 chain_context.json → 末尾 CHAIN_NEXT:FACTOR1C
Agent C2 → 读取 chain_context → 写 1C+2 → 更新 chain_context → 末尾 CHAIN_NEXT:FACTOR3
Agent C3 → 读取 chain_context → 写 3 → 更新 chain_context → 末尾 CHAIN_NEXT:FACTOR4
Agent C4 → 读取完整 chain_context + 报告草稿 → 写 4+最终输出 → 回扫ES → 移除所有占位符
```

`chain_context.json` 至少包含：`parameter_anchors`、`factor1b_key_judgments`、`capital_intensity_view`、`moat_evidence_used`、`growth_quality_flags`、`valuation_constraints`、`open_questions_for_later_agents`、`executive_summary_inputs`。

### 1.3 质量门：数量+内容双重验证

每个Agent完成后：
- **行数门**：新增行数 ≥ 目标×50%（低于则重试1次，仍低则标注⚠️）
- **关键词门**：grep特定章节标题，缺失则判定"未执行"
- **数字溯源门**：citation_verifier.py（最终报告）

---

## 2. 全流程架构

```
用户: "分析 01502.HK 港股通"
        ↓
┌────────────────────────────────────────────────────────────────┐
│  Phase 0：输入解析与确认                                        │
│  ① 解析代码/公司名/渠道/PDF                                    │
│  ② AskUserQuestion（缺少信息时触发）                           │
│  ③ 创建 output/{code}_{name}/ 目录                            │
└───────────────────────┬────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Phase 1：数据采集（Python，自动）                   │
│  ┌──────────────────┐  ┌──────────────────────────┐ │
│  │  Phase 1A:       │  │  Phase 1B:               │ │
│  │  Python脚本      │  │  Zone B LLM提取          │ │
│  │  · compute_bundle│  │  · 读pdf_sections.json   │ │
│  │  · financial_    │  │  · 运行Zone B 5个提取器  │ │
│  │    trends        │  │  · 输出mda/seg/risks/    │ │
│  │  · (PDF下载/解析)│  │    gov/audit.json        │ │
│  └──────────────────┘  └──────────────────────────┘ │
│  两者并行运行，等待全部完成                            │
└───────────────────────┬─────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Phase 1.5：数据门禁（data_gate.py）                 │
│  L1 EXIST → L2 SANITY → L3 CROSS → L4 FRESH        │
│  PASS → 继续 | WARN → 继续+标注 | BLOCK → 修复      │
└───────────────────────┬─────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Phase 2：Zone J 判断层（LLM，并行4个）             │
│  · moat_agent → moat_assessment.json               │
│  · capex_agent → capex_classification.json         │
│  · earnings_quality_agent → earnings_quality.json  │
│  · data_quality_agent → data_discount.json         │
│  · boundary_validator --boundary zone_j            │
│    （只允许参数+证据+置信度；禁止叙事结论进入C）   │
│  完成后：cross_validator + compute_bundle_precise   │
│         + rule_engine                               │
└───────────────────────┬─────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Phase 3：Zone C 4-Agent写作链（顺序执行）          │
│                                                     │
│  Agent C1 → 报告头部 + 因子1A + 因子1B（9模块）    │
│  输出：zone_c_C1_output.md + chain_context.json     │
│  [行数门] ≥ 600行 | [关键词门] 模块〇-9             │
│           ↓                                         │
│  Agent C2 → 读取 chain_context → 因子1C + 因子2    │
│  输出：更新 chain_context                           │
│  [行数门] ≥ 600行 | [关键词门] 增量ROIC + Q税率    │
│           ↓                                         │
│  Agent C3 → 读取 chain_context → 因子3             │
│  输出：更新 chain_context                           │
│  [行数门] ≥ 800行 | [关键词门] AA序列 + GG三档     │
│           ↓                                         │
│  Agent C4 → 读取完整 chain_context → 因子4 + ES回扫│
│  [行数门] ≥ 800行 | [关键词门] DDM + 仓位 + ES填充  │
└───────────────────────┬─────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Phase 3.5：报告质量门禁                            │
│  · 章节完整性检查（12个必须存在的二级标题）         │
│  · 财务趋势速览是否包含完整IS/BS/CF表格            │
│  · Executive Summary是否已由C4回扫填写              │
│  PASS → 继续 | BLOCK → 补充后重新门禁（最多1次）    │
└───────────────────────┬─────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  Phase 4：后处理                                    │
│  · citation_verifier.py（数字溯源验证）             │
│  · report_to_html.py（可选，生成HTML）              │
│  · 交付报告路径给用户                               │
└─────────────────────────────────────────────────────┘
```

---

## 3. Phase 0：输入解析与 AskUserQuestion

### 3.1 输入格式

用户可以输入以下组合：

| 输入 | 示例 | 说明 |
|------|------|------|
| 股票代码 | `01502.HK` / `600887` | 优先 |
| 公司名称 | `金融街物业` / `伊利股份` | 需查DB确认 |
| 渠道 | `港股通` / `直接` / `美股` | 决定Q税率 |
| PDF | 用户上传 | 触发Phase 1B |

### 3.2 AskUserQuestion 触发条件

| # | 触发条件 | 问题 | 选项 |
|---|---------|------|------|
| 1 | 港股 + 渠道未指定 | "通过什么渠道持有？" | 港股通(Q=20%) / 香港本地直投(Q=0%) / 其他 |
| 2 | 同一公司多地上市 | "分析哪个市场的股票？" | 港股({代码}) / A股({代码}) |
| 3 | 模糊公司名（多个匹配） | "确认您要分析的公司" | {公司1} / {公司2} |
| 4 | DB无数据 | "DB中无此股票数据，是否继续？" | 上传数据后继续 / 仅用PDF分析 |
| 5 | PDF不足3年 | "年报PDF不足，是否自动下载？" | 自动下载 / 跳过（降级） / 稍后上传 |

**不触发**：完整代码 + 完整渠道 → 直接执行；A股默认长期持有(Q=10%)。

---

## 4. Phase 3：Zone C 写作链详细规格

### 4.1 单文件渐进写入模型

所有 Agent 写同一个报告文件（`{output_dir}/{公司}_{代码}_分析报告.md`），通过 CHAIN_NEXT 占位符传递：

```
创建时（Agent C1起始）：
  # 龟龟投资策略 · 分析报告
  ## 报告元信息 ... （C1写）
  ## Executive Summary
  ⚠️ [C4_PLACEHOLDER: Agent C4完成后回扫填写]
  ## 关键假设汇总 ... （C1写）
  ## 财务趋势速览 ... （C1写）
  ## 一、因子1A ... （C1写）
  ## 二、因子1B ... （C1写）
  CHAIN_NEXT:FACTOR1C

Agent C2：定位 CHAIN_NEXT:FACTOR1C → 追加写入 → 留 CHAIN_NEXT:FACTOR3
Agent C3：定位 CHAIN_NEXT:FACTOR3  → 追加写入 → 留 CHAIN_NEXT:FACTOR4
Agent C4：定位 CHAIN_NEXT:FACTOR4  → 追加写入 → 回扫ES → 移除所有占位符
```

### 4.2 各 Agent 行数目标与质量门

| Agent | 负责章节 | 目标行数 | 最低行数 | 必须包含的关键词 |
|-------|---------|:---:|:---:|---------|
| C1 | 报告头部4节 + 1A + 1B | 800-1,200 | **600** | `模块〇`, `模块3`, `模块9`, `财务趋势速览`, `## Executive Summary` |
| C2 | 1C + 2 | 600-800 | **400** | `增量ROIC`, `G系数`, `Q税率三档`, `R(NP)`, `R(OE)` |
| C3 | 3（步骤1-13） | 800-1,200 | **600** | `AA序列`, `GG三档`, `Lambda`, `误差传播`, `步骤13` |
| C4 | 4 + 最终输出 + ES | 800-1,000 | **600** | `DDM`, `阶梯买入`, `否决门总览`, `Executive Summary` |

### 4.3 行数校验与反压缩机制

```python
# 协调器在每个Agent完成后执行
def validate_agent_output(agent_id, report_file, prev_lines):
    current_lines = count_lines(report_file)
    new_lines = current_lines - prev_lines
    
    target_min = AGENTS[agent_id]["min_lines"]
    
    # 行数检查
    if new_lines < target_min * 0.5:
        print(f"⚠️ {agent_id}: 仅新增{new_lines}行（目标≥{target_min*0.5}行）")
        return "TOO_SHORT"
    
    # 关键词检查
    keywords = AGENTS[agent_id]["required_keywords"]
    report_text = read_file(report_file)
    missing = [kw for kw in keywords if kw not in report_text]
    if missing:
        print(f"⚠️ {agent_id}: 缺少关键内容: {missing}")
        return "MISSING_KEYWORDS"
    
    return "PASS"

# 重试规则
def maybe_retry(agent_id, result, retry_count):
    if result in ("TOO_SHORT", "MISSING_KEYWORDS") and retry_count < 1:
        print(f"🔄 {agent_id}: 重试（第{retry_count+1}次）")
        return True  # 重新运行Agent
    elif result != "PASS":
        print(f"⚠️ {agent_id}: {result}（已重试1次，继续但标注警告）")
        return False  # 继续但标注
    return False
```

### 4.4 Agent 超时规则

| Agent | 软超时 | 硬超时 | 超时行为 |
|-------|:---:|:---:|---------|
| C1 | 8分钟 | 12分钟 | 输出已有内容，标注`⚠️ 超时截断` |
| C2 | 6分钟 | 10分钟 | 同上 |
| C3 | 8分钟 | 12分钟 | 同上 |
| C4 | 8分钟 | 12分钟 | 同上，ES标注`⚠️ 需手工完善` |

**禁止任何Agent存活超过15分钟**（极端情况）。

---

## 5. Phase 3.5：报告质量门禁

### 5.1 必须存在的12个二级标题

```python
REQUIRED_SECTIONS = [
    "## 报告元信息",
    "## Executive Summary",
    "## 关键假设汇总",
    "## 财务趋势速览",
    "## 一、因子",   # 因子1A
    "## 二、因子",   # 因子1B
    "## 三、因子",   # 因子1C
    "## 四、因子",   # 因子2
    "## 五、因子",   # 因子3
    "## 六、因子",   # 因子4
    "## 七、最终",   # 最终综合输出
    "## 八、风险",   # 风险提示
]
```

### 5.2 质量检查清单

| 检查项 | 判定方法 | 不通过行为 |
|--------|---------|-----------|
| 12节完整性 | grep各标题 | BLOCK → 补写缺失节 |
| 财务趋势速览含完整表格 | 检查是否有5年的 `\|` 表格 | WARN |
| Executive Summary已填写 | 检查是否含`C4_PLACEHOLDER`字符串 | BLOCK → C4重新回扫 |
| 因子3步骤1-13存在 | grep "步骤1" 到 "步骤13" | WARN |
| 否决门总览存在 | grep "否决门总览" | WARN |
| 报告总行数 | wc -l > 1,500行 | WARN；< 1,000行 → BLOCK |

### 5.3 处理逻辑

```
if BLOCK 数量 > 0:
    → 启动补充Agent，修复BLOCK项（最多1次）
    → 重跑Phase 3.5
    → 仍有BLOCK → 标注⚠️，继续Phase 4（不再重试）

if 仅有WARN:
    → 继续Phase 4，在报告末尾附上质量警告列表
```

---

## 6. 协调器文件结构（实现规划）

### 6.1 两个协调器文件

| 文件 | 作用 | 使用方式 |
|------|------|---------|
| `strategies/turtle/coordinator_v5.md` | Claude对话协调器（指令文档）| Claude读取并执行 |
| `scripts/run_pipeline.py` | Python自动化协调器 | 命令行执行 |

两者职责互补：
- **coordinator_v5.md**：Claude在对话中使用，处理判断性任务（Zone B/J LLM调用、Zone C写作、AskUserQuestion、质量决策）
- **run_pipeline.py**：自动化Python任务（Zone A计算、文件管理、数据门禁Python检查、状态跟踪）

### 6.2 coordinator_v5.md 结构

```markdown
# 龟龟投资策略 V5.3 协调器

## 角色与职责
## 输入解析
## AskUserQuestion触发矩阵
## Phase 0：确认与目录创建
## Phase 1：数据采集（调用Python脚本 + Zone B LLM提取）
## Phase 1.5：数据门禁
## Phase 2：Zone J判断层（4个并行LLM判断）
## Phase 3：Zone C写作链（调用规范）
## Phase 3.5：报告质量门禁
## Phase 4：后处理与交付
## 异常处理矩阵
## 文件路径约定
## 数据单位约定
```

### 6.3 run_pipeline.py 升级点

| 当前问题 | 升级内容 |
|---------|---------|
| LLM步骤是"手动" | 增加inline LLM调用选项（`--auto-llm`）调用Claude API |
| 无报告组装 | 增加Step 12：`zone_c_chain.py --assemble` 将C1-C4拼接成最终报告 |
| 状态机被文件欺骗 | 增加内容哈希检查（输入文件hash变化 → 强制重跑该步骤） |
| 无质量门禁 | 增加Step 11.5：调用quality_gate.py（Phase 3.5检查） |
| 无超时 | 增加subprocess超时参数 |

---

## 7. 对比：新版 vs 旧版 vs 当前V5.2

| 功能 | 旧版 v2.25 | 当前 V5.2 | 新版 V5.3 |
|------|:---:|:---:|:---:|
| AskUserQuestion | ✅ | ❌ | ✅ |
| LLM自动调用 | ✅ | ❌（全手动） | ✅ |
| CHAIN_NEXT单文件渐进写入 | ✅ | ❌（分4文件） | ✅ |
| 行数校验+反压缩 | ✅（v2.32） | 🟡（只FAIL不重试） | ✅ |
| Agent超时机制 | ✅（v2.33） | ❌ | ✅ |
| Phase 2.5 数据门禁 | ✅ | ✅ | ✅ |
| Phase 3.5 报告质量门 | ✅ | ❌ | ✅ |
| 报告组装（C1-C4→最终） | ✅（单文件不需组装） | ❌ | ✅ |
| Executive Summary回扫 | ✅ | ❌ | ✅ |
| Zone A Python计算 | ❌（LLM计算） | ✅ | ✅ |
| Zone B 结构化提取 | ❌（LLM读全文） | ✅ | ✅ |
| Zone J 判断层 | ❌ | ✅ | ✅ |
| Citation Verifier | ❌ | ✅ | ✅ |
| 财务趋势速览（235行） | ✅ | ❌ | ✅（C1负责） |
| 幻觉防控 | 差（LLM直读年报） | 好（Python Zone A） | 最好 |
| 报告信息量 | 高（127KB） | 低（44-63KB） | 目标 ≥ 100KB |

---

## 8. 实现优先级（Coordinator相关）

| 优先级 | 任务 | 解决的问题 |
|--------|------|---------|
| **P0** | 写 `coordinator_v5.md`（完整指令文档） | Claude对话时无指导文件 |
| **P0** | `run_pipeline.py` 增加 Step 12（报告组装） | C1-C4输出从未变成最终报告 |
| **P1** | `run_pipeline.py` 增加 Step 11.5（质量门禁） | 无章节完整性检查 |
| **P1** | `run_pipeline.py` 增加内容哈希状态跟踪 | 修改prompt后需手动删文件 |
| **P2** | `run_pipeline.py --auto-llm` 选项 | LLM步骤仍需手动 |
| **P2** | 行数校验增加自动重试（不只是FAIL） | 短输出无自动修复 |
