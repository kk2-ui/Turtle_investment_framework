"""核心 Agent 循环 — 单 Agent + 工具调用，替代 V10 多 Agent 并行。

借鉴 Dayu "LLM in the loop" 架构：
- Agent 在统一上下文中逐步分析
- 按需调用工具获取数据（不预先推送全量数据）
- 写 → 审 → 修 在统一消息流中完成

Usage::

    from turtle_agent import LlmClient, ToolRegistry, TurtleAgent, AgentConfig

    client = LlmClient(provider="anthropic")
    tools = ToolRegistry()
    # ... register tools ...

    config = AgentConfig(code="06668.HK", contract_path="output/analysis_contract.json")
    agent = TurtleAgent(llm=client, tools=tools, config=config)
    report_path = agent.analyze()
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 抑制 macOS CoreGraphics PDF 渲染警告（无害）
import warnings
warnings.filterwarnings("ignore")
_original_stderr = sys.stderr
class _FilteredStderr:
    def write(self, s):
        if "Cannot set non-stroke color" not in s and "CoreGraphics" not in s:
            _original_stderr.write(s)
    def flush(self):
        _original_stderr.flush()
sys.stderr = _FilteredStderr()

from turtle_agent.llm_client import LlmClient, LlmResponse, ToolCall
from turtle_agent.tool_registry import ToolRegistry

_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------


@dataclass
class AgentConfig:
    """Agent 运行配置。

    Args:
        code: 股票代码（如 ``06668.HK``）。
        contract_path: 分析合约 JSON 路径。
        output_dir: 输出目录（默认与合约同目录）。
        max_iterations: 最大 Agent 循环迭代次数。
        max_tokens_per_call: 单次 LLM 调用最大输出 token。
        temperature: 采样温度。
        template_path: 报告模板路径。
    """

    code: str = ""
    contract_path: str = ""
    output_dir: str = ""
    max_iterations: int = 30
    max_tokens_per_call: int = 32768  # V12: 32K 支持深度章节写作
    temperature: float = 0.3
    template_path: str = "templates/report_template_v10.md"

    def __post_init__(self) -> None:
        if not self.output_dir and self.contract_path:
            self.output_dir = os.path.dirname(os.path.abspath(self.contract_path))


# ---------------------------------------------------------------------------
# TurtleAgent
# ---------------------------------------------------------------------------


class TurtleAgent:
    """单 Agent 分析循环。

    完整流程：
    1. 加载合约 + 模板 + 数据上下文
    2. 构建 system prompt + 初始用户消息
    3. While not finished: LLM Call → Tool Execute → Append Results
    4. 后处理：审计 → 组装报告

    Args:
        llm: LLM API 客户端。
        tools: 工具注册表。
        config: 运行配置。
    """

    def __init__(
        self,
        llm: LlmClient,
        tools: ToolRegistry,
        config: AgentConfig,
    ) -> None:
        self._llm: LlmClient = llm
        self._tools: ToolRegistry = tools
        self._config: AgentConfig = config
        self._messages: list[dict[str, Any]] = []
        self._iterations: int = 0
        self._context: dict[str, Any] = {}
        self._chapters: dict[int, str] = {}

    # ------------------------------------------------------------------
    # analyze — 主入口
    # ------------------------------------------------------------------

    def analyze(self) -> str:
        """执行完整分析，返回报告文件路径。

        Returns:
            生成的报告文件路径。

        Raises:
            RuntimeError: 关键步骤失败时抛出。
        """
        print(f"\n{'='*60}")
        print(f"🐢 TurtleAgent 分析启动: {self._config.code}")
        print(f"   合约: {self._config.contract_path}")
        print(f"   模型: {self._llm.model}")
        print(f"   工具: {len(self._tools)} 个")
        print(f"{'='*60}\n")

        start_time = time.time()

        # Step 1: 加载上下文
        self._load_context()

        # Step 2: 构建 system prompt
        system_prompt = self._build_system_prompt()

        # Step 3: 初始化消息
        self._messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"开始分析 {self._config.code}。"
                    f"所有工具调用的 output_dir 参数必须使用 "
                    f"'{self._config.output_dir}'。"
                    f"请先调用 list_documents 查看 '{self._config.output_dir}' 目录下的可用数据。"
                ),
            },
        ]

        # Step 4: Agent 循环
        self._run_loop()

        # Step 5: 组装报告
        report_path = self._assemble_report()

        elapsed = time.time() - start_time
        print(f"\n✅ 分析完成 ({elapsed:.1f}s): {report_path}\n")

        return report_path

    # ------------------------------------------------------------------
    # 上下文加载
    # ------------------------------------------------------------------

    def _load_context(self) -> None:
        """加载分析合约与数据上下文。"""
        # 加载合约
        with open(self._config.contract_path, encoding="utf-8") as f:
            self._context["contract"] = json.load(f)

        # 加载模板
        template_path = self._config.template_path
        if not os.path.isabs(template_path):
            # 相对路径：先试 CWD，再试 scripts/../
            if not os.path.exists(template_path):
                alt = os.path.join(_scripts_dir, "..", template_path)
                if os.path.exists(alt):
                    template_path = os.path.abspath(alt)
        if os.path.exists(template_path):
            with open(template_path, encoding="utf-8") as f:
                self._context["template_raw"] = f.read()
        else:
            self._context["template_raw"] = "(模板未找到，按标准龟龟结构写作)"

        # 加载数据文件（Zone A/B/J JSON）
        data_dir = self._config.output_dir
        json_files = [
            "compute_bundle.json",
            "financial_trends.json",
            "analysis_contract.json",
            "mda.json",
            "segments.json",
            "risks.json",
            "governance.json",
            "audit.json",
            "moat_assessment.json",
            "capex_classification.json",
            "earnings_quality.json",
            "data_discount.json",
        ]
        for jf in json_files:
            path = os.path.join(data_dir, jf)
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        self._context[jf.replace(".json", "")] = json.load(f)
                except (json.JSONDecodeError, OSError):
                    self._context[jf.replace(".json", "")] = {"_error": "parse_failed"}

        # V12: 加载定性摘要（如果存在）
        qual_path = os.path.join(data_dir, "qualitative_summary.json")
        if os.path.exists(qual_path):
            try:
                with open(qual_path, encoding="utf-8") as f:
                    self._context["qualitative_summary"] = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        # V12 P2: 模板预检
        template_text = self._context.get("template_raw", "")
        self._context["template_issues"] = []
        if template_text and "Part A" in template_text:
            try:
                from scripts.template_validator import validate_template
                from scripts.template_parser import parse_template
                layout = parse_template(template_text)
                issues = validate_template(layout)
                if issues:
                    self._context["template_issues"] = issues
            except Exception:
                pass

        # V12 P2: 数据边界验证
        self._context["data_warnings"] = []
        for jf in ["moat_assessment.json", "capex_classification.json", "earnings_quality.json"]:
            jpath = os.path.join(data_dir, jf)
            if os.path.exists(jpath):
                try:
                    from scripts.boundary_validator import validate_file
                    import json as _json
                    with open(jpath) as f:
                        data = _json.load(f)
                    # Basic validation: check key fields exist
                    warnings = []
                    if jf == "moat_assessment.json":
                        if "moat_evidence" not in data:
                            warnings.append("moat_assessment 缺少 moat_evidence")
                    elif jf == "earnings_quality.json":
                        if "non_recurring_items" not in data:
                            warnings.append("earnings_quality 缺少 non_recurring_items")
                    if warnings:
                        self._context["data_warnings"].extend(warnings)
                except Exception:
                    pass
        cb = self._context.get("compute_bundle", {})
        self._context["company_name"] = cb.get("company_name", self._config.code)
        self._context["ts_code"] = self._config.code

    def _build_resume_hint(self) -> str:
        """检查已有章节文件，生成断点续跑提示。"""
        import os as _os
        output_dir = self._config.output_dir
        existing = sorted([
            f for f in _os.listdir(output_dir)
            if f.startswith("_ch") and f.endswith(".md")
        ])
        if not existing:
            return ""
        chapters_done = [f.replace(".md", "") for f in existing]
        return f"""
- ⚠️ **断点续跑**: 已检测到 {len(existing)} 个已完成章节 ({', '.join(chapters_done[:5])}{'...' if len(chapters_done) > 5 else ''})
- 这些章节如果审计已通过，**不要重写它们**，直接跳过。只写缺失的章节。
- 如果某章审计未通过（文件存在但内容过短），才需要重写。"""

    # ------------------------------------------------------------------
    # System Prompt 构建
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        """构建 Agent system prompt。V12 模式自动检测。"""
        contract = self._context.get("contract", {})
        effective_years = contract.get("effective_years", [])
        cycle_type = contract.get("cycle_type", "未知")
        analysis_start = contract.get("analysis_start_year", "?")

        tool_list = "\n".join(
            f"- **{t['function']['name']}**: {t['function']['description']}"
            for t in self._tools.get_schemas()
        )

        company = self._context.get("company_name", self._config.code)
        template_raw = self._context.get("template_raw", "")
        is_v12 = "Part A" in template_raw and "定性深度分析" in template_raw
        version = "V12" if is_v12 else "V11"

        qual_context_block = ""
        if is_v12:
            qual_summary = self._context.get("qualitative_summary")
            qual_text = _format_qualitative_context(qual_summary) if qual_summary else "（定性分析尚未完成，请在定量分析前先完成 Part A 定性章节 Ch1-Ch9 的写作和摘要提取）"
            qual_context_block = f"""
## 定性分析上下文（V12 Dayu 桥接）

{qual_text}

若定性分析尚未完成，请先执行：逐章写入 Part A 的 Ch1-Ch9 定性章节 → 各章审计通过后 → 提取 qualitative_summary.json → 再进行 Part B 定量分析。
"""

        v12_methodology = ""
        if is_v12:
            v12_methodology = """
## V12 Dayu 定性分析方法论

本报告采用 Dayu 定性深度分析 + Turtle 定量估值的统一框架。

### 定性写作规范（Part A Ch1-Ch9）— 来自 Dayu write_chapter.md

**结构要求**：
- 每章必须包含三部分：**结论要点** / **详细情况** / **证据与出处**
- 结论要点用 bullet 简明扼要，让读者 30 秒抓住核心
- **「详细情况」用 `#### ` 四级标题分隔为子节**（如 `#### 核心产品与服务`）。禁止连续段落堆砌。

**证据格式**：
- 使用 `[source: 文件名 → 字段 = 值]` 精确格式（如 `[source: financial_trends.json → income_statement → 毛利率 FY2025=14.19%]`）
- 每章末尾的「证据与出处」用表格列出所有来源及其关键数据

**Bullet 格式要求（强制）**：
- bullet 下另起一行输出回答：第一行 bullet，另起一行输出回答正文，二者之间不留空行
- 严禁把 bullet 改写成非 bullet；禁止写成 `- 标签：回答` 格式
- 不得输出"只有 bullet、没有正文"的空条目
- 相邻 bullet 之间保留空行
- 禁止用数字编号（不要出现"1."）编排格式

**缺口处理**：
- 当某个信息必须保留但暂时无法给出来源时，使用统一占位符格式：
  `【占位符】（缺口：{缺失的具体信息} ｜ 需要：{需要什么类型的来源} ｜ 已检索范围：{已检索过的文档} ｜ 下一步：{建议的补强路径}）`

**条件规则（ITEM_RULE）**：
- 每条 ITEM_RULE 的 when 条件成立时才输出该条目
- 不成立时整项不输出，不解释、不占位
- 成立但无内容可输出时，整项不输出
- ITEM_RULE 只能增补正文，不能替代章节骨架里原本就要写的 bullet

**证据要求**：
- 本章末尾必须包含 `### 证据与出处` 小节
- **禁止笼统引用**：不要写 `[source: financial_trends.json]`。必须精确到字段名和值，格式：
  `[source: financial_trends.json → gross_margin FY2025=14.19%]`
  `[source: 01502_2025_年报.pdf MDA p.13 → 在管面积50.62M sqm]`
- GG/DDM 等定量结果必须展示**完整计算链路**：每个参数来源 + 计算步骤 + 最终值
- 只使用本章实际引用的数据源，不列无关来源

**读者指南（报告开头自动生成）**：
- 3 分钟读者 → 投资要点概览 + 综合决策
- 15 分钟读者 → 加 Ch1-Ch4（生意+行业+护城河+变化）+ Ch11-Ch12（GG+DDM）
- 验算读者 → 各章"证据与出处"定位到具体 JSON 字段/年报页码

**深度要求**：
- 有同行数据时用对比表，有财务数据时用趋势表。没有数据时不做机械填充。
- GG 计算注意：compute_bundle 中的市值可能因 yfinance 股本数据错误而偏小，请用 373.5M 股 × 最新股价 验证市值

### Facet 系统
模板中的 COMPANY_FACET_CATALOG 包含 36 种业务类型 + 25 种约束条件。
写作前先根据 financial_trends.json 和 segments.json 判断公司的主业务类型和关键约束，
然后在章节中优先使用匹配的 preferred_lens（认知口径）。

### 定性→定量桥接
完成 Part A 全部 9 章并审计通过后：
1. 读取所有定性章节，提取 qualitative_summary.json（包含 moat_rating, moat_sources, b_penalty_evidence, g_base_context, earnings_quality, data_discount_signals, veto_level_risks 等关键字段）
2. 这些字段将用于增强 Zone J 参数估计（moat/capex/earnings_quality/data_quality）

### 统一决策合成 — 来自 Dayu write_research_decision.md

## 分析基调
默认**保守偏空**——对乐观解释要求更高的证据标准，对悲观情景赋予更重的权重。具体判断框架见 CLAUDE.md。

**决策优先级规则（强制）**：
- 当定性决定与定量决定冲突时，**定量决定（GG/DDM/否决门）为第一优先**
- 定性决定只能调整仓位（Continue→仓位加满，Pause→仓位减半），不能在定量否决时"拉回"决策
- 禁止"取折中"——如果定量说 Avoid，最终必须是 Avoid 或 Strong Reject，不能变成 Hold

Part C 的 Ch13 综合决策使用 5 状态合成矩阵：

| | Turtle Buy | Turtle Hold | Turtle Avoid |
|---|---|---|---|
| **Dayu Continue** | Strong Buy | Cautious Watch | 好公司太贵 |
| **Dayu Pause** | 价格错配 | Hold Review | Likely Avoid |
| **Dayu Abandon** | 数据冲突 | Slow Fade | Strong Reject |

**决策写作约束（强制）**：
- 先用前文章节完成当前判断，不要重新检索全公司
- 默认只写 1 条主判断链；只有第二条判断链独立且缺一不可时，才写第 2 条
- 默认写两个阈值事件：一个最关键的升级阈值 + 一个最关键的降级或终止阈值
- 不要为了显得果断而硬下结论——真实的不确定比虚假的确定更有价值

**价值陷阱处理（强制）**：
- 每个价值陷阱检查项必须给出方向判断和置信度（高/中/低），**不能留空**
- 格式：`低PB+ROE恶化：ROE从39%→9%，接近社会平均。概率低（置信度中），因为经营性杠杆有限`

**竞争性解释（强制）**：
- 当核心变量存在多种解释时，**必须给出概率判断**（百分比）
- 每种解释必须标注：**验证方法**（什么数据能证伪）+ **验证时间窗口**
- 格式：`解释A（拐点）概率30%，解释B（均值回归）概率50%，解释C（粉饰）概率20%。FY2026 H1 毛利率>14%可排除解释C`

**决策回退条件（替代"止损"）**：
- 区分建仓前/建仓后：
  - 已建仓 → 止损价 + 基本面止损条件
  - 未建仓 → "升级跟踪"条件（什么信号触发建仓）+ "移除跟踪"条件（什么信号放弃）
"""

        return f"""# 龟龟策略分析师 ({version})

你是龟龟投资策略的**唯一分析师**。你拥有完整的分析上下文和工具集。
按顺序逐步完成分析，主动调用工具获取所需数据。

## 分析标的
- 代码: {self._config.code}
- 公司: {company}
- 数据目录: {self._config.output_dir}
- 周期分类: {cycle_type}
- 有效分析窗口: {effective_years}（起始: {analysis_start}）
{self._build_resume_hint()}
{qual_context_block}
{v12_methodology}
## 分析方法论
1. **了解数据**: 调用 list_documents 查看可用文档
2. **读取 Zone B 洞察（优先）**: 调用 read_zone_data(mda/segments/risks/governance/audit)
   这些 JSON 已提炼关键结论+数据+证据引用，信息密度远高于原始 PDF。
   若某 zone 不存在，再用 read_section 读原始 PDF 补充。
3. **提取财务**: 调用 get_financial_statement 和 get_financial_trends 获取定量数据
4. **定量计算**: 调用 compute_gg、compute_ddm、assess_moat 完成估值
5. **写作报告**: 按模板合约逐章写入（write_chapter），每章写完后审计（audit_chapter）
6. **最终决策**: 综合各因子给出最终结论
7. **组装报告**: 调用 assemble_report 生成完整报告

## 模板合约要求
{template_raw if template_raw else '（模板未加载，按标准龟龟报告结构写作）'}

## 写作深度原则
**深度来自数据可用性，不是固定数字。有数据的领域写深，没数据的领域不强行编造。**
- 优先用表格承载对比数据。纯文字段落不宜连续超过 5 行。
- 护城河、财务趋势、风险等核心章节的深度由 available data 决定，不由"必须写 X 个子节"驱动。
- 参见模板各章的 CHAPTER_CONTRACT + ITEM_RULE 了解具体该覆盖哪些方面。

## 写作流程（重要）
**每章写作前**，必须调用工具重读该章相关数据，不要依赖记忆：
- 定性章(Ch1-Ch9): 先调 **get_peer_comparison** + get_financial_trends + read_zone_data 刷新上下文
  - Ch2-3 行业/护城河章：必须调用 get_peer_comparison 获取同行列表+百分位排名
  - 护城河分析**必须引用百分位数据**（如'毛利率 P16，显著低于行业中位数 19.19%'），不得只做定性描述
  - 每定性章至少嵌入 **1 张同行/行业对比表**（≥4 家可比公司 × ≥5 项指标）
- 定量章(Ch10-Ch13): 先调 **compute_data_quality** + **get_market_data** + **compute_aa** + compute_gg/compute_ddm
  - Ch11 GG 章：**禁止**只输出最终 GG 数字。必须执行以下流程：
  1. 调 compute_gg → 从 `ingredients` 字段逐一列出 8 个原料（值+来源+可信度）
  2. 原料表标注每个值的来源（DB computed / DB fallback / yfinance corrected / Zone J）
  3. **自己展开公式**：GG = [NP] × [M] × (1-[Q]) / [MC] + [g_adj]，代入原料表，写出每一步
  4. 与 compute_gg 的 gg_base 交叉验证。若偏差>1pp，标注"⚠️ Agent 验算偏差"
  5. M 值溯源：若 M_source 含 "fallback"，必须在报告中警示→"实际分红数据不可得，使用行业默认 X%，GG 可能偏高约 Ypp"
  6. HH 偏离：|R(NP)-GG| 值 + 判定。>3pct→因子2不适用
  7. MC 修正：若 MC.corrected=true，标注"yfinance 股本已用数据库修正"
  8. 对标海螺水泥 2864 行报告的 GG 精算深度。每少一个环节，audit 必须判 REGENERATE。
  - Ch11 结尾必须做**反向压力测试**：列出至少 2 个能让 GG<II 的极端情景及所需条件。如果所有合理情景均不改变方向，结论更可信。
  - 报告需引用 compute_data_quality 的完整性得分（对标海螺'36/36字段，0%折价'）
  - GG 计算前必须调 get_market_data 检查股本数据可信度，yfinance 股本不准时用年报数据修正
- **写完一章 → 立即 audit_chapter → 不通过就当场重写 → 再审计 → 直到通过，才能写下一章**
  - 不允许攒到全部写完再批量审计——那会导致"发现了违规但不修"
  - 若审计返回 passed=false 或 verdict=regenerate，必须立即重写该章（不要跳到下一章）
  - 重写时要比上一版多 50%+ 的量化数据、表格和 [source:] 证据引用
  - E1 证据密度不足 → 每条数字声明都要加 [source:] 锚点，不要只加一两个对付过去

## 写作约束
- **所有数据断言必须附带 [source: 文件名] 证据锚点**
- 缺失数据标注 "⚠️ 数据不可用"，禁止编造数字
- 金额单位: 百万元 RMB
- 数值保留 1 位小数

## 可用工具
{tool_list}

## 重要提示
- 不要一次性读完所有数据——按需调用工具
- 工具返回的数据可能很大（如 read_section 可能返回数万字），请合理使用
- 如果工具返回 error，记录错误并尝试其他方式获取数据
- 目标产出: 一份完整的分析报告"""

    # ------------------------------------------------------------------
    # Agent 循环
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """主循环：LLM 调用 → 工具执行 → 结果注入 → 继续。"""
        tool_schemas = self._tools.get_schemas()

        while self._iterations < self._config.max_iterations:
            self._iterations += 1

            print(f"  [{self._iterations}] LLM 调用...", end=" ", flush=True)
            call_start = time.time()

            try:
                resp = self._llm.chat(
                    self._messages,
                    tools=tool_schemas,
                    temperature=self._config.temperature,
                    max_tokens=self._config.max_tokens_per_call,
                )
            except RuntimeError as exc:
                print(f"\n❌ LLM 调用失败: {exc}")
                break

            elapsed = time.time() - call_start
            print(
                f"{elapsed:.1f}s "
                f"(in:{resp.usage.get('input',0)} out:{resp.usage.get('output',0)})"
            )

            # 工具调用
            if resp.has_tool_calls:
                self._handle_tool_calls(resp)
                continue

            # 纯文本（可能已完成，或需要继续）
            if resp.is_text_only:
                self._messages.append(
                    {"role": "assistant", "content": resp.content}
                )
                # 检查是否应该结束
                if self._check_completion():
                    break
                # 追加继续提示
                self._messages.append({
                    "role": "user",
                    "content": "请继续完成剩余的章节。如果所有章节已完成，请调用 assemble_report 组装最终报告。",
                })
                continue

        if self._iterations >= self._config.max_iterations:
            print(f"  ⚠️ 达到最大迭代次数 ({self._config.max_iterations})，强制结束")

    def _handle_tool_calls(self, resp: LlmResponse) -> None:
        """处理 LLM 返回的工具调用。"""
        # 添加 assistant 消息（含 tool_use blocks）
        # Anthropic 格式：content 是 list of blocks
        self._messages.append({
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                }
                for tc in resp.tool_calls
            ],
        })

        # 执行工具并添加结果
        tool_results: list[dict[str, Any]] = []
        for tc in resp.tool_calls:
            print(f"    🔧 {tc.name}({_summarize_args(tc.arguments)})", end=" ")
            result = self._tools.execute(tc.name, tc.arguments)
            ok = result.get("ok", False)
            icon = "✅" if ok else "❌"
            value = result.get("value", result.get("error", ""))
            preview = str(value)[:80] if ok else str(value)[:80]
            print(f"{icon} {preview}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

        self._messages.append({
            "role": "user",
            "content": tool_results,
        })

    def _check_completion(self) -> bool:
        """检查 Agent 是否已完成分析。"""
        last_msg = self._messages[-1]
        content = ""
        if isinstance(last_msg.get("content"), str):
            content = last_msg["content"].lower()
        elif isinstance(last_msg.get("content"), list):
            for block in last_msg["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    content += block.get("text", "").lower()

        # 检测完成信号
        if "assemble_report" in str(self._messages[-2:]).lower():
            return True
        if "报告已完成" in content or "分析完成" in content:
            return True

        return False

    # ------------------------------------------------------------------
    # 报告组装
    # ------------------------------------------------------------------

    def _assemble_report(self) -> str:
        """组装最终报告。"""
        # 提取各章节内容
        # 章节内容可能存在于消息流中，也可能通过 write_chapter 工具写入文件
        output_dir = self._config.output_dir
        os.makedirs(output_dir, exist_ok=True)
        code_short = self._config.code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")

        # 扫描已写入的章节文件
        chapter_files = sorted(
            f for f in os.listdir(output_dir)
            if f.startswith("_ch") and f.endswith(".md")
        )

        # 组装
        parts: list[str] = [
            f"# {self._context.get('company_name', '')} ({self._config.code}) 龟龟策略分析报告",
            "",
            "> 由 TurtleAgent V12 单 Agent 工具循环生成 | Dayu定性+Turtle定量",
            f"> 分析日期: {time.strftime('%Y-%m-%d')}",
            "",
        ]

        for cf in chapter_files:
            path = os.path.join(output_dir, cf)
            with open(path, encoding="utf-8") as f:
                parts.append(f.read())
                parts.append("")

        # 从消息中提取来源清单
        parts.append("## 来源清单")
        parts.append("")
        sources = self._extract_sources()
        for src in sources:
            parts.append(f"- {src}")
        if not sources:
            parts.append("（无显式来源引用）")

        report_content = "\n".join(parts)
        report_path = os.path.join(output_dir, f"{code_short}_分析报告_v12.md")

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        return report_path

    def _extract_sources(self) -> list[str]:
        """从消息流中提取 [source: X] 引用。"""
        import re

        sources: set[str] = set()
        pattern = re.compile(r"\[source:\s*([^\]]+)\]")
        for msg in self._messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                sources.update(pattern.findall(content))
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        sources.update(pattern.findall(block.get("text", "")))
        return sorted(sources)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------


def _summarize_args(args: dict[str, Any], max_len: int = 60) -> str:
    """生成工具调用参数摘要。"""
    parts = [f"{k}={_truncate(str(v))}" for k, v in list(args.items())[:3]]
    summary = ", ".join(parts)
    return summary[:max_len] + ("..." if len(summary) > max_len else "")


def _truncate(s: str, max_len: int = 40) -> str:
    """截断字符串。"""
    s = s.replace("\n", " ").strip()
    return s[:max_len] + ("..." if len(s) > max_len else "")


# ------------------------------------------------------------------
# V12: 定性摘要格式化
# ------------------------------------------------------------------


def _format_qualitative_context(qualitative_summary: dict | None) -> str:
    """将 qualitative_summary.json 格式化为 prompt 可用的文本。"""
    if not qualitative_summary:
        return "（未提供定性分析上下文）"

    parts: list[str] = []

    ch3 = qualitative_summary.get("ch3_business_model", {})
    if ch3:
        parts.append("**护城河与商业模式**")
        parts.append(f"- 评级: {ch3.get('moat_rating', 'N/A')}")
        parts.append(f"- 来源: {', '.join(ch3.get('moat_sources', []))}")
        parts.append(f"- 证据: {ch3.get('moat_evidence_summary', 'N/A')}")
        parts.append(f"- b_penalty: {ch3.get('b_penalty_evidence', 'N/A')}")
        parts.append(f"- g_base上下文: {ch3.get('g_base_context', 'N/A')}")
        parts.append("")

    ch6 = qualitative_summary.get("ch6_financial_performance", {})
    if ch6:
        parts.append("**财务表现**")
        parts.append(f"- 盈利质量: {ch6.get('earnings_quality', 'N/A')} — {ch6.get('earnings_quality_notes', '')}")
        nri = ch6.get("non_recurring_items", [])
        if nri:
            parts.append(f"- 非经常项: {', '.join(nri)}")
        parts.append("")

    ch8 = qualitative_summary.get("ch8_governance", {})
    if ch8:
        parts.append("**治理**")
        parts.append(f"- 评级: {ch8.get('governance_rating', 'N/A')}")
        signals = ch8.get("data_discount_signals", [])
        if signals:
            parts.append(f"- 数据折扣信号: {', '.join(signals)}")
        parts.append("")

    ch9 = qualitative_summary.get("ch9_risks", {})
    if ch9:
        veto = ch9.get("veto_level_risks", [])
        if veto:
            parts.append("**否决级风险**")
            for v in veto:
                parts.append(f"- {v.get('risk', '?')}")
            parts.append("")

    return "\n".join(parts) if parts else "（定性摘要为空）"
