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
import re
import sys
import time
from copy import deepcopy
from datetime import datetime
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

try:
    from turtle_agent._version import REPORT_VERSION, CHAPTERS_SUBDIR, REPORTS_SUBDIR
except ImportError:
    REPORT_VERSION  = "v13"
    CHAPTERS_SUBDIR = "chapters"
    REPORTS_SUBDIR  = "reports"
from turtle_agent.tool_registry import ToolRegistry

_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_workspace_root = Path(__file__).resolve().parents[3]
_niangao_root = _workspace_root / "_niangao"
if _niangao_root.is_dir() and str(_niangao_root) not in sys.path:
    sys.path.insert(0, str(_niangao_root))


def _load_text_file(path: str) -> str:
    if not os.path.exists(path):
        return ''
    try:
        with open(path, encoding='utf-8') as f:
            return f.read().strip()
    except OSError:
        return ''


# 综合派估值框架的 canonical 文档（单一真相源）。
# 这两份文件同时被 Claude/prompts 路径与 DeepSeek 执行路径读取——
# 从源头消除「双树断裂」：改 canonical 文档即同时改两条链路。
_GRAHAM_FRAMEWORK_ROOT = Path(__file__).resolve().parents[2] / "prompts" / "references"
_GRAHAM_LITE_FILE = _GRAHAM_FRAMEWORK_ROOT / "_graham_framework_lite.md"
_GRAHAM_R5_FILE = _GRAHAM_FRAMEWORK_ROOT / "factor_R5回报率分解.md"


def _load_graham_framework() -> str:
    """装载综合派估值 + R5 回报分解框架，供 system prompt 注入。

    文件缺失时优雅降级为空串（回退到模板自带的 GG/DDM 纪律，不报错）。
    """
    lite = _load_text_file(str(_GRAHAM_LITE_FILE))
    r5 = _load_text_file(str(_GRAHAM_R5_FILE))
    if not lite and not r5:
        return ''
    parts = ["\n### 综合派估值与回报框架（canonical，来自 prompts/references/）\n"]
    parts.append(
        "本节是 Greenwald《价值投资：从格雷厄姆到巴菲特》综合派方法的执行卡。"
        "**估值裁决层以此为准**：GG/DDM 工具产出的原料表（NP/OE/FCF/M/Q/MC/g_adj/II/Rf）"
        "是本框架的输入料，最终 IV / V_cash / V_final / λ / 回报安全边际按下述流程组装。\n"
    )
    if lite:
        parts.append("\n#### 【估值主框架 · 六路由 + λ 综合】\n\n" + lite)
    if r5:
        parts.append("\n#### 【R5 回报率分解 · 含④b 双重税负】\n\n" + r5)
    return "\n".join(parts)


def _judgment_first_prompt_block(role: str) -> str:
    """Return the compact judgment-first contract for active runtime roles."""
    common = """## 判断优先宪法（高优先级）
- 在证据、PIT、结果隔离和权限边界这些硬约束内，首要产物是对企业经济和投资处理有用的最佳当前判断；审计完整、状态码和过门本身不是产物。
- 将已验证事实与经济推论分开。允许基于事实形成有边界、可证伪的推论；缺少因果权限只限制因果主张，不得抹掉其他企业判断。
- `UNKNOWN`、`MIXED`、`NO_PRIMARY`、`MEASUREMENT_MISMATCH`只属于受影响的主张。材料性未知必须转成保守区间、情景、条件结论、投资后果或能区分解释的下一观察。
- 区分“证据/推论置信度”和“经营结果概率”。没有校准基准时使用定性置信度，不得为显得果断而编造百分比。
- 读者语言先写经济结论，再把限制贴到对应主张；不得用治理说明、权限免责声明或状态码墙代替判断。"""
    addenda = {
        "research": """- 你不拥有整家公司或最终投资综合权，但凡finding接触材料性企业证据，仍必须写出局部经济含义、最强替代解释、区分结果，以及在权限内的valuation/action影响。仅返回`PUBLIC_INFO_UNAVAILABLE`或缺口清单不算完成。""",
        "synthesis": """- 你负责形成复核后的最佳当前综合：说明决定性机制、最强替代解释、企业或投资后果及翻转条件。只因足以改变中心判断的错误而退回；局部缺口优先局部降级，不新增全局门。""",
        "report": """- 围绕少数决定性问题给出方向性或条件性裁决、最强反方和翻转条件，并把判断传播到企业质量、永久损失、owner cash、估值或本任务权限内的处理。未证实的增长选择权不进基准情景，不等于价值为零或经营失败。""",
    }
    if role not in addenda:
        raise ValueError(f"unknown judgment-first runtime role: {role}")
    return common + "\n" + addenda[role]


def _load_asset_template_supplements(contract: dict[str, Any]) -> list[dict[str, str]]:
    asset = contract.get('asset_profile', {}) if isinstance(contract, dict) else {}
    names = list(asset.get('recommended_templates', []) or [])
    if str(asset.get('analysis_mode') or 'stock') == 'stock':
        if 'technical_appendix.md' not in names:
            names.append('technical_appendix.md')
    base = Path(__file__).resolve().parents[2] / 'shared' / 'qualitative' / 'templates'
    items = []
    for name in names:
        path = base / name
        if path.exists():
            items.append({'name': name, 'content': _load_text_file(str(path))})
    return items


_V13_CHAPTER_TITLES = {
    0: "投资要点概览",
    1: "公司做的是什么生意",
    2: "行业吸引力与公司位置",
    3: "商业模式机制、护城河与关键约束",
    4: "最近一年关键变化与当前阶段",
    5: "经营表现与核心驱动",
    6: "财务表现与资本配置",
    7: "股东回报路径",
    8: "管理层、治理与激励",
    9: "核心风险与否决项",
    10: "增长质量与参数校准",
    11: "穿透回报率 GG",
    12: "内在价值合成与裁决",
    13: "DDM 估值与仓位执行",
    14: "综合决策",
}


def _template_sections_for_targets(template: str, targets: tuple[int, ...]) -> str:
    """Return only target chapter contracts for a repair-pass prompt."""
    sections: list[str] = []
    for idx in targets:
        title = _V13_CHAPTER_TITLES.get(idx)
        if not title:
            continue
        match = re.search(rf"^## {re.escape(title)}\s*$", template, re.MULTILINE)
        if not match:
            continue
        next_heading = re.search(r"^## ", template[match.end():], re.MULTILINE)
        end = match.end() + next_heading.start() if next_heading else len(template)
        sections.append(template[match.start():end].strip())
    return "\n\n---\n\n".join(sections)


def _compact_template_index(template: str) -> str:
    """Build a small global map; full chapter contracts are disclosed on demand."""
    lines = [
        "完整模板不在系统提示中重复展开。本轮开始时一次调用 "
        "`read_report_contract_pack` 加载全部目标章合同；随后逐项执行各章 "
        "CHAPTER_CONTRACT、ITEM_RULE 与输出骨架。已加载合同包时不要逐章重复读取。",
        "",
        "| 章节 | 标题 |",
        "|---:|---|",
    ]
    for idx, title in _V13_CHAPTER_TITLES.items():
        present = bool(re.search(rf"^## {re.escape(title)}\s*$", template, re.MULTILINE))
        lines.append(f"| Ch{idx} | {title}{'' if present else '（模板缺失）'} |")
    return "\n".join(lines)


def _chapter_memory(content: str, chapter_index: int, *, max_chars: int = 1800) -> str:
    """Preserve thesis-bearing chapter facts while dropping the full Markdown body."""
    text = str(content or "").strip()
    if not text:
        return f"Ch{chapter_index}: 无可用记忆"
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = next((line.lstrip("# ").strip() for line in raw_lines if line.startswith("#")), f"Ch{chapter_index}")
    selected: list[str] = []
    in_conclusion = False
    for line in raw_lines:
        if re.match(r"^#{2,4}\s+", line):
            heading = line.lstrip("# ").strip()
            in_conclusion = any(key in heading for key in ("结论", "判断", "一眼看懂", "决策"))
            continue
        if line.startswith(("<!--", "END_", "```", "|---")):
            continue
        is_signal = bool(re.search(
            r"\d|%|GG|DDM|II|ROE|OCF|AA|FCFE|风险|护城河|治理|资本配置|"
            r"因此|意味着|导致|取决于|否决|升级|降级|观察|回避|买入|持有",
            line,
            re.IGNORECASE,
        ))
        if in_conclusion or is_signal:
            clean = re.sub(r"\s+", " ", line)
            if clean not in selected:
                selected.append(clean)
        if len("\n".join(selected)) >= max_chars - len(title) - 80:
            break
    if not selected:
        selected = [re.sub(r"\s+", " ", line) for line in raw_lines[:8]]
    body = "\n".join(selected)
    memory = f"[公司全局记忆·Ch{chapter_index} {title}]\n{body}"
    return memory[:max_chars]


def _identity_ledger(context: dict[str, Any]) -> dict[str, Any]:
    """Return the compact identities that must survive every chapter transition."""
    bundle = context.get("compute_bundle") if isinstance(context.get("compute_bundle"), dict) else {}
    factor2 = bundle.get("factor2") if isinstance(bundle.get("factor2"), dict) else {}
    factor3 = bundle.get("factor3") if isinstance(bundle.get("factor3"), dict) else {}
    factor4 = bundle.get("factor4") if isinstance(bundle.get("factor4"), dict) else {}
    params = bundle.get("params") if isinstance(bundle.get("params"), dict) else {}
    return {
        "company": context.get("company_name"),
        "code": context.get("ts_code"),
        "II": params.get("II", bundle.get("II")),
        "Rf": params.get("Rf", bundle.get("Rf")),
        "GG_AA": (factor3.get("gg") or {}).get("base") if isinstance(factor3.get("gg"), dict) else None,
        "GG_FCFE": (factor3.get("gg_fcfe") or {}).get("base") if isinstance(factor3.get("gg_fcfe"), dict) else None,
        "GG_NORMALIZED": (factor3.get("gg_normalized") or {}).get("base") if isinstance(factor3.get("gg_normalized"), dict) else None,
        "GG_DISCOUNTED": (factor3.get("gg_discounted") or bundle.get("gg_discounted") or {}).get("base") if isinstance(factor3.get("gg_discounted") or bundle.get("gg_discounted"), dict) else None,
        "dividend_identity": factor4.get("dividend_identity"),
        "DDM": factor4.get("ddm") or bundle.get("ddm"),
        "P_BASE": factor4.get("p_base") or bundle.get("p_base"),
        "current_pe": factor4.get("current_pe"),
        "factor2_rejection": factor2.get("rejection") or bundle.get("rejection"),
    }



_TRACKING_REPORT_LABELS = {
    'annual': '年报',
    'q1': '一季报',
    'h1': '中报',
    'q3': '三季报',
}


def _load_json_file(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _safe_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _normalize_tracking_report_type(value: Any) -> str:
    text = str(value or '').strip().lower()
    return text if text in _TRACKING_REPORT_LABELS else 'annual'


def _tracking_label(value: Any) -> str:
    return _TRACKING_REPORT_LABELS.get(_normalize_tracking_report_type(value), '年报')


def _extract_report_summary(path: str, *, max_chars: int = 220) -> str:
    text = _load_text_file(path)
    if not text:
        return ''
    parts: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('```') or line.startswith('---'):
            continue
        line = line.lstrip('#').strip()
        if not line or line.startswith('|'):
            continue
        line = line.replace('**', '').replace('`', '')
        parts.append(line)
        if len(' / '.join(parts)) >= max_chars:
            break
    summary = ' / '.join(parts)
    return summary[:max_chars] + ('...' if len(summary) > max_chars else '')


def _build_tracking_context(output_dir: str, contract: dict[str, Any], compute_bundle: dict[str, Any]) -> dict[str, Any]:
    tracking = contract.get('tracking') if isinstance(contract.get('tracking'), dict) else {}
    report_type = _normalize_tracking_report_type(tracking.get('report_type') or contract.get('report_type'))
    fiscal_year = _safe_int(tracking.get('fiscal_year') or contract.get('fiscal_year'))
    period_end = str(tracking.get('period_end') or contract.get('period_end') or '').strip()[:10] or None
    metric_basis = str(tracking.get('metric_comparison_basis') or contract.get('metric_comparison_basis') or ('unavailable' if report_type == 'annual' else 'yoy'))
    change_classification = str(tracking.get('change_classification') or contract.get('change_classification') or '')
    comparison_summary = str(tracking.get('comparison_summary') or contract.get('comparison_summary') or '')

    previous_contract = _load_json_file(os.path.join(output_dir, 'analysis_contract.latest.json'))
    previous_bundle = _load_json_file(os.path.join(output_dir, 'compute_bundle.latest.json'))
    previous_summary = _extract_report_summary(os.path.join(output_dir, '最新_分析报告_v12.md'))

    annual_contract = _load_json_file(os.path.join(output_dir, 'analysis_contract.latest_annual.json'))
    annual_bundle = _load_json_file(os.path.join(output_dir, 'compute_bundle.latest_annual.json'))
    annual_summary = _extract_report_summary(os.path.join(output_dir, '最新年报_分析报告_v12.md'))

    current_bundle = compute_bundle if isinstance(compute_bundle, dict) else {}
    current_gg = (current_bundle.get('gg_discounted') or {}).get('base') or (current_bundle.get('gg') or {}).get('base')
    current_ddm = (current_bundle.get('ddm') or {}).get('fair_value')
    annual_gg = (annual_bundle.get('gg_discounted') or {}).get('base') or (annual_bundle.get('gg') or {}).get('base')
    annual_ddm = (annual_bundle.get('ddm') or {}).get('fair_value')
    annual_pbase = ((annual_bundle.get('p_base') or {}).get('price_native') or (annual_bundle.get('p_base') or {}).get('price_hkd'))
    annual_upside = (annual_bundle.get('p_base') or {}).get('upside_pct')

    previous_tracking = previous_contract.get('tracking') if isinstance(previous_contract.get('tracking'), dict) else {}
    annual_tracking = annual_contract.get('tracking') if isinstance(annual_contract.get('tracking'), dict) else {}

    # V12.20: 读 _comparison.json（Agent 在上一轮 save_comparison 写入的，或本次已写入的）
    comparison_data = {}
    comp_path = os.path.join(output_dir, '_comparison.json')
    if os.path.exists(comp_path):
        try:
            with open(comp_path, encoding='utf-8') as fh:
                comparison_data = json.load(fh).get('comparison', {})
        except Exception:
            pass

    # 从上一节点 bundle 提取 core_thesis 和 key_risks
    prev_thesis = ''
    prev_risks = []
    prev_plan = previous_bundle.get('investment_plan', {}) if isinstance(previous_bundle, dict) else {}
    if not prev_plan:
        # investment_plan 可能在独立文件中
        plan_path = os.path.join(output_dir, '..',
            os.path.basename(os.path.dirname(previous_contract.get('_source_path', '')))
            if previous_contract.get('_source_path') else '',
            'investment_plan.json')
    prev_thesis = prev_plan.get('core_thesis', '') if isinstance(prev_plan, dict) else ''
    prev_risks = prev_plan.get('stop_loss_conditions', []) if isinstance(prev_plan, dict) else []
    if isinstance(prev_risks, str):
        prev_risks = [r.strip() for r in prev_risks.split('\n') if r.strip()][:5]

    return {
        'output_dir': output_dir,
        'current': {
            'report_type': report_type,
            'report_type_label': _tracking_label(report_type),
            'fiscal_year': fiscal_year,
            'period_end': period_end,
            'metric_comparison_basis': metric_basis,
            'change_classification': change_classification,
            'comparison_summary': comparison_summary,
            'gg': current_gg,
            'ddm': current_ddm,
        },
        'previous_latest': {
            'report_type': _normalize_tracking_report_type(previous_contract.get('report_type') or previous_tracking.get('report_type')) if previous_contract else None,
            'report_type_label': _tracking_label(previous_contract.get('report_type') or previous_tracking.get('report_type')) if previous_contract else None,
            'fiscal_year': _safe_int(previous_contract.get('fiscal_year') or previous_tracking.get('fiscal_year')) if previous_contract else None,
            'period_end': str(previous_contract.get('period_end') or previous_tracking.get('period_end') or '').strip()[:10] or None,
            'summary': previous_summary,
            'core_thesis': prev_thesis or (previous_summary or '')[:200],
            'key_risks': prev_risks,
            'gg': (previous_bundle.get('gg_discounted') or {}).get('base') or (previous_bundle.get('gg') or {}).get('base') if previous_bundle else None,
            'ddm': (previous_bundle.get('ddm') or {}).get('fair_value') if previous_bundle else None,
        },
        'latest_annual': {
            'report_type_label': _tracking_label('annual') if annual_contract else None,
            'fiscal_year': _safe_int(annual_contract.get('fiscal_year') or annual_tracking.get('fiscal_year')) if annual_contract else None,
            'period_end': str(annual_contract.get('period_end') or annual_tracking.get('period_end') or '').strip()[:10] or None,
            'summary': annual_summary,
            'gg': annual_gg,
            'ddm': annual_ddm,
            'p_base': annual_pbase,
            'upside_pct': annual_upside,
        },
        'quarterly_comparison': comparison_data,
    }


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
    max_chapter_attempts_per_pass: int = 2
    temperature: float = 0.3
    template_path: str = "templates/report_template_v10.md"
    pass_name: str = "build"
    repair_targets: tuple[int, ...] = ()
    source_deepening: bool = False
    binding_only: bool = False
    publish_downstream: bool = True
    run_id: str = ""
    judgment_task_id: str = ""
    judgment_task_resume: bool = False
    judgment_synthesis: bool = False
    synthesis_only: bool = False
    pit_mode: bool = False
    pit_production_mode: bool = False
    pit_case_id: str = ""
    pit_experiment_id: str = ""
    pit_cutoff_at: str = ""
    analysis_purpose: str = "INVESTMENT_DECISION"

    def __post_init__(self) -> None:
        self.analysis_purpose = str(self.analysis_purpose or "INVESTMENT_DECISION").upper()
        if self.analysis_purpose not in {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}:
            raise ValueError("analysis_purpose invalid")
        if not self.output_dir and self.contract_path:
            self.output_dir = os.path.dirname(os.path.abspath(self.contract_path))
        if self.binding_only:
            # Binding repair is chapter clerical work.  Callers cannot
            # accidentally re-enable source gates or the read-only synthesis path.
            self.source_deepening = False
            self.synthesis_only = False


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
        # 每个 fresh-context pass 独立计数。短章也属于真实尝试，否则会出现
        # Ch1/Ch2 各重写八次、挤占后半段 token 预算的退化。
        self._chapter_write_counts: dict[int, int] = {}
        self._usage: dict[str, int] = {
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_hit_input_tokens": 0,
            "cache_miss_input_tokens": 0,
        }
        self._call_usage: list[dict[str, Any]] = []
        self._chapter_attempt_log: list[dict[str, Any]] = []
        self._context_chars_compacted: int = 0
        self._duplicate_result_chars_compacted: int = 0
        self._chapter_contract_chars_compacted: int = 0
        self._chapter_contract_reads: set[int] = set()
        self._passed_chapters: set[int] = set()
        if self._config.synthesis_only:
            self._passed_chapters.update(self._config.repair_targets)
        self._chapter_memories: dict[int, str] = {}
        self._source_research_calls: list[dict[str, Any]] = []
        # A source gate may reject an otherwise complete, expensive chapter
        # draft.  Retain exactly one latest candidate per chapter and replay it
        # deterministically once the missing reads are satisfied; do not ask
        # the model to regenerate thousands of tokens merely because tool-call
        # ordering was imperfect.
        self._pending_source_blocked_writes: dict[int, dict[str, Any]] = {}
        # assemble_report 是 pass 的提交动作。无论完成契约是否通过，都应把
        # 控制权交还给外层 orchestrator，由它开启 fresh-context repair。
        self._assembled_this_pass: bool = False
        self._judgment_handoff_requested: bool = False
        self._loop_error: str = ""
        self._decision_already_frozen: bool = False
        self._last_offered_tool_names: set[str] = set()
        self._structured_rejection_state: dict[str, tuple[str, int]] = {}
        self._structured_rejection_totals: dict[str, int] = {}
        self._offstage_structured_calls: int = 0
        self._structured_no_progress_error: str = ""
        self._initial_structured_frontier: str = (
            self._structured_repair_frontier()[0] if self._config.synthesis_only else ""
        )
        self._structured_frontier_completed: bool = False
        self._pit_report_path: str = ""

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
        if self._config.pit_mode:
            return self._analyze_pit()
        if self._config.pit_production_mode:
            return self._analyze_pit_production()

        task_type = (
            "challenger" if self._config.judgment_synthesis
            else "deep_research" if self._config.judgment_task_id
            else "report_repair" if self._config.repair_targets
            else "report_synthesis"
        )
        if self._llm is not None and hasattr(self._llm, "set_runtime_task"):
            self._llm.set_runtime_task(task_type)

        print(f"\n{'='*60}")
        print(f"🐢 TurtleAgent 分析启动: {self._config.code}")
        print(f"   合约: {self._config.contract_path}")
        print(f"   模型: {self._llm.model}")
        print(f"   工具: {len(self._tools)} 个")
        print(f"{'='*60}\n")

        start_time = time.time()

        # Step 1: 加载上下文
        self._load_context()
        if (
            not self._config.judgment_task_id
            and not self._config.judgment_synthesis
            and not self._config.binding_only
        ):
            self._initialize_research_execution()

        # Step 2: 构建 system prompt
        system_prompt = (
            self._build_judgment_task_system_prompt()
            if self._config.judgment_task_id
            else self._build_judgment_synthesis_system_prompt()
            if self._config.judgment_synthesis
            else self._build_system_prompt()
        )

        # Step 3: 初始化消息
        decision_already_frozen = False
        if self._config.judgment_task_id:
            action = "继续" if self._config.judgment_task_resume else "开始"
            opening_task = (
                f"{action}定向研究任务 {self._config.judgment_task_id}。"
                "严格按system中的剩余工具、预算和mutation_scope执行；"
                "不要重新分析整家公司，不要组装报告。完成证据读取及必要的限定写回后，"
                "必须调用 complete_judgment_research_task。"
            )
        elif self._config.judgment_synthesis:
            opening_task = (
                "独立复核全部定向研究finding，并调用finalize_judgment_research_review"
                "原子提交完整评审与综合结论。"
                "不得新增搜索、不得修改章节或决策参数、不得组装报告。"
            )
        elif self._config.repair_targets:
            targets = ", ".join(f"Ch{i}" for i in self._config.repair_targets)
            try:
                decision_ledger = json.loads(
                    Path(self._config.output_dir, "decision_ledger.json").read_text(
                        encoding="utf-8"
                    )
                )
            except (OSError, json.JSONDecodeError):
                decision_ledger = {}
            decision_already_frozen = bool(
                (decision_ledger.get("freeze") or {}).get("frozen")
            )
            self._decision_already_frozen = decision_already_frozen
            synthesis_batch = bool({0, 14}.intersection(self._config.repair_targets))
            if synthesis_batch and not decision_already_frozen:
                decision_instruction = (
                    "目标章节处理完后调用 write_decision_manifest 固化唯一决策身份，再调用 "
                    "write_decision_ledger 固化全部canonical参数，再调用 write_claim_evidence_ledger "
                    "校验重大主张证据链，然后调用 write_valuation_model_ledger 验证模型适用性与脆弱性，"
                    "再调用 write_financial_driver_bridge 固化公司经营驱动、现金转换与资本配置到模型和动作的传导，"
                    "再调用 write_thesis_test_ledger 固化竞争解释、阈值和概率，调用 write_decisive_question_findings "
                    "闭环全部入选问题，随后调用 write_insight_ledger、write_judgment_review 与 "
                    "plan_judgment_research，最后调用 assemble_report。"
                )
            elif synthesis_batch:
                decision_instruction = (
                    "decision manifest/ledger 已冻结，不得改写其 canonical 值；依次更新或验证 "
                    "write_claim_evidence_ledger、write_valuation_model_ledger、write_financial_driver_bridge、write_thesis_test_ledger、"
                    "write_decisive_question_findings 与 write_insight_ledger，再调用 write_judgment_review、"
                    "plan_judgment_research 和 assemble_report。"
                )
            else:
                decision_instruction = (
                    "本轮是普通章节批次，决策与研究综合全部冻结：禁止调用任何 write_*_ledger、"
                    "write_decisive_question_findings、write_judgment_review、plan_judgment_research 或 assemble_report；"
                    "目标章节全部通过后立即结束本上下文，结构化综合由后续 Ch14/Ch0 专用轮完成。"
                )
            opening_task = (
                f"开始 {self._config.code} 的自动质量修复轮（{self._config.pass_name}）。"
                f"本轮只处理完成契约阻断章节：{targets}。"
                "先调用 list_documents，再读取目标章和 audit；随后一次调用 "
                f"read_report_contract_pack(chapter_indexes={list(self._config.repair_targets)})；"
                "逐章执行合同包内 research_plan：回答全部研究问题，给出支持证据与反证，形成事实→机制→财务→估值闭环；"
                "保留已有有效内容，仅针对 blocking_rules 和研究计划缺口补深度、证据或缺失推导，"
                "并以 force_rewrite=true 写回。不要改写未列出的通过章节。"
                + decision_instruction
            )
            if self._config.binding_only:
                opening_task = (
                    f"开始 {self._config.code} 的 canonical 绑定最小修复轮（{self._config.pass_name}）。"
                    f"只处理章节：{targets}。第一轮同时调用 read_structured_ledger_contract(ledger='decision_binding')、"
                    f"read_report_contract_pack(chapter_indexes={list(self._config.repair_targets)})、目标章节读取和audit，"
                    "取得 active canonical 值、全部验证错误及写回合同。"
                    "只允许删除错误身份锚点、把现有数值绑定到正确 D-id，或给不同情景/不同口径数值添加合法 "
                    "[valuation: model_id] 等身份；不得重新研究、扩写、删减实质分析、改变任何数值、结论、"
                    "估值参数、仓位或触发器。以 force_rewrite=true 最小写回并让 write_chapter 的 "
                    "decision_binding_validation 通过。禁止调用年报、网页、计算和任何 write_*_ledger 工具；"
                    "目标章通过后立即结束当前上下文。"
                )
            if self._config.synthesis_only:
                frontier_tool, frontier_validation = self._structured_repair_frontier()
                frontier_findings = [
                    *list(frontier_validation.get("invalid_findings") or []),
                    *list(frontier_validation.get("incomplete_findings") or []),
                ]
                opening_task = (
                    f"开始 {self._config.code} 的结构化综合专用轮（{self._config.pass_name}）。"
                    "现有 Ch0/Ch14 正文及所有已通过章节均已冻结；禁止调用 write_chapter、"
                    "禁止网页泛搜或全文重研。只读取现有章节、审计和证据账本；"
                    "如果结构化工具明确因官方事实缺失而拒绝，可用read_section做有界原文补证。"
                    "结构化工具可确定性追加canonical引用块，这不属于模型改写正文。"
                    + (
                        f"当前唯一允许修复的结构化前沿是 {frontier_tool}；"
                        "不要调用任何下游ledger、decisive research、judgment或assemble工具。"
                        "先读取该ledger精确合同和现有VERIFIED观察，只修以下阻断，"
                        "最多提交两次；通过后框架会自动开放下一前沿："
                        + " | ".join(map(str, frontier_findings[:20]))
                        if frontier_tool else
                        "全部结构化前沿已通过，可继续最终评审与assemble。"
                    )
                    + decision_instruction
                )
            if self._config.source_deepening and not self._config.synthesis_only:
                opening_task += (
                    " 本轮是来源驱动深化，不是形式补字。写章前必须实际调用 read_section 阅读至少两个财年的年报原文，"
                    "逐章执行 research_plan 的 primary_sections 和 required_tools：只在该章要求时做三组 search_report，"
                    "或用 web_search 搜索至少两个竞争、渠道/行业问题并 web_fetch 至少一篇可靠正文。"
                    "每次 read_section/search_report/web_search/web_fetch 都必须传 research_for_chapters=[当前章节号]；"
                    "只有同一材料确实服务多个章时才可列多个章节，未绑定章节的网页与检索不计入来源门。"
                    "微信/Sogou/雪球等社交或搜索中转页不能作为唯一 web_fetch 正文，须回到官网、监管、行业机构或可复核直接页面。"
                    "裸写工具名不算来源；外部事实必须标注真实域名和发布日期。"
                    "本轮列出的每一个目标章都必须 force_rewrite 写回并通过；不得因旧报告已经 COMPLETE 而提前 assemble。"
                    "来源深化还启用章节身份对应的证据覆盖门；新增材料必须服务于研究问题、因果链、反证或公式/情景，"
                    "但不按篇幅和分析单元数量加分。write_chapter 未通过时只补真实缺口。"
                )
                if set(self._config.repair_targets).intersection({10, 11, 12, 13, 14}):
                    opening_task += (
                        " 定量裁决章存在严格财报前置项：读取合同后，必须先用read_section完成最近两个财年的"
                        "STMT和NOTES原文，并绑定当前目标章；在这四次有效读取完成前，不要反复search_report、"
                        "不要读取非必要网页，也不要尝试write_chapter。完成前置项后再调用计算、估值和框架工具，"
                        "把剩余上下文留给推导与一次完整写回。"
                    )
        else:
            opening_task = (
                f"开始分析 {self._config.code}。"
                "请在首次响应同时调用 list_documents 和 read_report_contract_pack，"
                "一次获得完整报告蓝图与逐章研究计划，然后完成全部章节；不要逐章重复读取合同。"
            )
            if self._config.source_deepening:
                opening_task += (
                    " 本次为来源驱动的高质量生成：每章写作前必须完成合同包指定的年报原文读取，"
                    "覆盖至少两个财年；只在研究计划要求时做定向报告检索或网页搜索，"
                    "且 web_search 后必须 web_fetch 读取可靠正文。每次 read_section/search_report/web_search/web_fetch "
                    "必须传 research_for_chapters=[服务的章节号]；只有确实共用时才列多个章。"
                    "微信/Sogou/雪球等社交或搜索中转页不计作合格的唯一外部正文。"
                    "读取记录由工具层按章节落盘，正文声称‘已读’不算完成。"
                )

        self._messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    opening_task
                    + " "
                    f"所有工具调用的 output_dir 参数必须使用 "
                    f"'{self._config.output_dir}'。"
                ),
            },
        ]

        # Step 4: Agent 循环
        self._run_loop()

        if self._loop_error:
            raise RuntimeError(f"LLM循环失败，禁止用后续完成契约掩盖原始错误: {self._loop_error}")
        if self._structured_no_progress_error:
            raise RuntimeError(self._structured_no_progress_error)

        if self._config.judgment_task_id:
            state = self._judgment_task_state()
            task_status = state.get("task_status")
            if task_status == "COMPLETE":
                return str(Path(self._config.output_dir) / "judgment_research_execution.json")
            if task_status == "VIOLATION":
                raise RuntimeError(
                    f"定向研究任务 {self._config.judgment_task_id} 违反执行契约: "
                    + "; ".join(state.get("violations") or [])
                )
            reason = self._loop_error or "fresh_context_pass_exhausted_before_task_completion"
            raise RuntimeError(
                f"定向研究任务 {self._config.judgment_task_id} 已保留断点，等待续跑: {reason}"
            )

        if self._config.judgment_synthesis:
            synthesis = self._load_judgment_synthesis()
            if synthesis.get("state") == "REVIEWED":
                return str(Path(self._config.output_dir) / "judgment_research_synthesis.json")
            reason = self._loop_error or "independent_review_not_finalized"
            raise RuntimeError(f"定向研究独立综合尚未完成: {reason}")

        # 研究计划一旦形成，当前全文上下文立即交棒。独立任务完成前禁止
        # 在这个已被整家公司材料占满的上下文继续研究或组装。
        if self._judgment_handoff_requested:
            return str(Path(self._config.output_dir) / "judgment_research_execution.json")

        if self._config.source_deepening and self._config.repair_targets and not self._config.synthesis_only:
            missing_targets = sorted(set(self._config.repair_targets) - self._passed_chapters)
            if missing_targets:
                raise RuntimeError(
                    "来源驱动深化未覆盖全部目标章节，禁止提交："
                    + ", ".join(f"Ch{idx}" for idx in missing_targets)
                )

        # Step 5: 组装报告（唯一出口在 write_tools.assemble_report）。
        report_path = self._assemble_report()

        elapsed = time.time() - start_time
        completion_path = os.path.join(self._config.output_dir, "completion_report.json")
        completion = {}
        if os.path.exists(completion_path):
            with open(completion_path, encoding="utf-8") as handle:
                completion = json.load(handle)
        status = completion.get("status", "INCOMPLETE") if isinstance(completion, dict) else "INCOMPLETE"
        if status in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
            print(f"\n✅ 分析完成 ({elapsed:.1f}s): {report_path}\n")
        else:
            print(f"\n❌ 分析未通过完成契约 ({elapsed:.1f}s): {report_path}\n")

        # draft 只用于后续自动 repair pass，禁止提前同步到 portfolio.db。
        if status not in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
            return report_path
        if not self._config.publish_downstream:
            print("  🧪 验证模式：跳过 _niangao 入库与仪表盘刷新")
            return report_path

        # V12.18: 写入 _niangao/portfolio.db + 刷新仪表盘
        try:
            od = os.path.abspath(self._config.output_dir)
            cb_path = os.path.join(od, "compute_bundle.json")
            contract_path = os.path.join(od, "analysis_contract.json")
            stock_dir = os.path.basename(od)
            ingest_bin = _niangao_root / "bin" / "niangao-ingest"
            if ingest_bin.exists():
                import subprocess as _sp
                ingest_env = {**os.environ, "PYTHONPATH": str(_niangao_root)}
                ingest_python = os.environ.get("NIANGAO_PYTHON")
                if not ingest_python:
                    candidate = _workspace_root / "Turtle_investment_framework" / ".venv" / "bin" / "python"
                    if candidate.exists():
                        ingest_python = str(candidate)
                if ingest_python:
                    ingest_env["NIANGAO_PYTHON"] = ingest_python
                result = _sp.run(
                    [
                        str(ingest_bin),
                        "--bundle", cb_path,
                        "--contract", contract_path,
                        "--stock-dir", stock_dir,
                    ],
                    cwd=str(_niangao_root),
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env=ingest_env,
                )
                if result.returncode == 0:
                    stdout = (result.stdout or "").strip()
                    if stdout:
                        print(stdout)
                    _sp.run(
                        [ingest_env.get("NIANGAO_PYTHON", sys.executable), "-m", "niangao.dashboard"],
                        cwd=str(_niangao_root),
                        capture_output=True,
                        timeout=60,
                        env=ingest_env,
                    )
                else:
                    err = (result.stderr or result.stdout or "").strip()
                    raise RuntimeError(err or f"niangao-ingest exited with {result.returncode}")
        except Exception as e:
            print(f"  ⚠️ _niangao 更新失败: {e}")

        return report_path

    def _analyze_pit(self) -> str:
        """Run a deliberately small writer context inside the PIT boundary."""
        allowed_tools = {
            "pit_list_sources",
            "pit_read_source",
            "pit_read_framework",
            "pit_write_report",
        }
        registered_tools = set(self._tools.list_tools())
        if registered_tools != allowed_tools:
            raise RuntimeError(
                "PIT writer 必须只注册受限读取和写入工具: "
                + ", ".join(sorted(registered_tools))
            )
        if not self._config.code or not self._config.pit_case_id or not self._config.pit_experiment_id:
            raise RuntimeError("PIT writer 缺少 code/case/experiment identity")
        if self._llm is None:
            raise RuntimeError("PIT writer 需要 LLM client")
        if hasattr(self._llm, "set_runtime_task"):
            self._llm.set_runtime_task("pit_writer")
        self._messages = [
            {"role": "system", "content": self._build_pit_system_prompt()},
            {
                "role": "user",
                "content": (
                    f"为 {self._config.code} 在 {self._config.pit_cutoff_at} 的信息集写PIT草案。"
                    "先列出来源，再阅读框架和支撑实质主张的来源；"
                    "最后只调用 pit_write_report 提交唯一草案。"
                ),
            },
        ]
        self._run_loop()
        if self._loop_error:
            raise RuntimeError(f"PIT writer 未完成: {self._loop_error}")
        if not self._pit_report_path:
            raise RuntimeError("PIT writer 在未写入草案前结束")
        return self._pit_report_path

    def _build_pit_system_prompt(self) -> str:
        """Keep PIT writer instructions independent from normal report context."""
        return f"""你在执行严格的历史时点研究写作。

公司身份：{self._config.code}
案例：{self._config.pit_case_id}
实验：{self._config.pit_experiment_id}
信息截止：{self._config.pit_cutoff_at}

你只能使用列出的四个工具。先调用 pit_list_sources；只可按 source_id 调用
pit_read_source，且只可按 allowlist 路径调用 pit_read_framework。禁止网页、搜索、
行情、当前价格、数据库、普通报告工具、任意路径和任何结算资料。

报告只能陈述已读取来源支持的事实；不确定处保留 UNKNOWN。不得给出投资收益、
买点、选股、仓位或事后结论。完成后调用 pit_write_report 一次：正文必须含有下列
独立标题，并在每个实质来源主张处使用精确的 `[source: source_id]`：

- `## Point-in-time scope`
- `## Evidence`
- `## Business and financial implications`
- `## Unknowns and monitoring`

正文说明这是冻结前的工程草案，而非已经通过完整生产质量门的报告。"""

    @staticmethod
    def _pit_production_allowed_tools(
        analysis_purpose: str = "INVESTMENT_DECISION",
    ) -> set[str]:
        allowed = {
            "pit_list_sources", "pit_read_source", "pit_read_framework",
            "pit_verify_official_fact", "pit_write_chapter", "pit_read_chapter",
            "pit_read_report_contract_pack", "pit_read_judgment_generation_handoff",
            "pit_read_structured_ledger_contract",
            "pit_audit_chapter", "pit_write_claim_evidence_ledger",
            "pit_write_financial_driver_bridge",
            "pit_write_thesis_test_ledger",
            "pit_write_insight_ledger", "pit_write_judgment_review", "pit_assemble_report",
        }
        if analysis_purpose == "INVESTMENT_DECISION":
            allowed.update({
                "pit_write_decision_manifest", "pit_write_decision_ledger",
                "pit_write_valuation_model_ledger", "pit_write_decisive_question_findings",
            })
        return allowed

    def _analyze_pit_production(self) -> str:
        """Generate a full report through PIT reads and output-bound V3 writes."""
        if set(self._tools.list_tools()) != self._pit_production_allowed_tools(self._config.analysis_purpose):
            raise RuntimeError("PIT production writer 工具集不完整或包含越界入口")
        if not self._config.code or not self._config.pit_case_id or not self._config.pit_experiment_id:
            raise RuntimeError("PIT production writer 缺少 code/case/experiment identity")
        if self._llm is None:
            raise RuntimeError("PIT production writer 需要 LLM client")
        if hasattr(self._llm, "set_runtime_task"):
            self._llm.set_runtime_task("pit_production_freeze")
        purpose_instruction = (
            "再读取pit_read_report_contract_pack，并以其中judgment_generation_handoff为统一入口；必要时调用pit_read_judgment_generation_handoff刷新RESEARCH_AGENDA和INVESTMENT_ENRICHMENT。"
            "必须原样继承同cutoff公司判断的中心路径、经营FJ、pair/card及正常化盈利/owner-cash传导；"
            "估值、条件回报和动作只能附加在该经营判断之后，若需要修改经营机制则停止本投资版本并先重做CJO；完成章节、估值后经营驱动桥和其余账本；"
            "每项材料FJ必须绑定主/反 pair 的唯一 signal，每个材料 pair 必须有复用既有案例卡的 transfer card；近失效反例若没有可验证 PIT episode，必须标记 UNKNOWN 且 card 只能 QUESTION_ONLY；账本冻结后调用pit_read_judgment_generation_handoff(view=JUDGMENT_SYNTHESIS)复核自然语言综合输入，再调用pit_assemble_report。"
            if self._config.analysis_purpose == "INVESTMENT_DECISION" else
            "再读取pit_read_report_contract_pack，并以其中judgment_generation_handoff.research_agenda为统一研究入口；必要时调用pit_read_judgment_generation_handoff刷新RESEARCH_AGENDA。"
            "READY_WITH_NO_PRIOR只表示可从官方证据继续，不表示选择判断或冻结完成。完成章节后先以 freeze=false 写入含计划 FJ ID 的 claim bootstrap，继而按 financial_driver→thesis→claim(freeze=true promote)→insight→judgment review 顺序冻结四层经营驱动桥、竞争反方、3—5条前瞻判断与案例 card；若无独立同定义 episode 或外部频率，thesis 必须写 probability_mode=NO_PROBABILITY、空 probability_sets 和完整双边 FJ/pair：没有 cutoff 前方向性证据则 NO_PRIMARY 且不写 central_path，有 P24 定向证据才用 selection_basis 作定性选择，绝不可填主观权重；仅 QUALIFIED_PROBABILITY 才可填概率及可追溯校准依据。近失效反例没有可验证 PIT episode 时必须 UNKNOWN/QUESTION_ONLY。账本冻结后调用pit_read_judgment_generation_handoff(view=JUDGMENT_SYNTHESIS)检查自然语言综合输入，再调用pit_assemble_report。"
        )
        purpose_boundary = (
            "CJO 严禁写入或讨论价格、估值、回报、仓位、交易动作、模型或 D-id；它只学习公司机制和可结算经营后果。"
            if self._config.analysis_purpose == "COMPANY_JUDGMENT_ONLY" else ""
        )
        system_prompt = (
            f"你在生成 {self._config.code} 的完整历史时点冻结报告。案例 {self._config.pit_case_id}，"
            f"实验 {self._config.pit_experiment_id}，截止 {self._config.pit_cutoff_at}，"
            f"用途 {self._config.analysis_purpose}。"
            "只可使用提供的PIT工具：先读取官方来源，数值事实用pit_verify_official_fact逐页验证，"
            + purpose_instruction
            + "需要修复结构化账本时只用pit_read_structured_ledger_contract。禁止网页、行情、数据库、任意路径、"
            "cutoff后资料和事后结论。来源不足时保留UNKNOWN，且不得由UNKNOWN推出买点、收益、选股或仓位。"
            + purpose_boundary
            + "章节中的[source: ...]只能填写本次pit_read_source已经读取的精确source_id；"
            "不得填写文件路径、URL、doc_id或未读取来源。"
        )
        self._messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "开始受限生产冻结。"},
        ]
        self._run_loop()
        if self._loop_error:
            raise RuntimeError(f"PIT production writer 未完成: {self._loop_error}")
        if not self._pit_report_path:
            raise RuntimeError("PIT production writer 在未组装报告前结束")
        return self._pit_report_path

    # ------------------------------------------------------------------
    # 上下文加载
    # ------------------------------------------------------------------

    def _load_context(self) -> None:
        """加载分析合约与数据上下文。"""
        # 加载合约
        with open(self._config.contract_path, encoding="utf-8") as f:
            self._context["contract"] = json.load(f)
        self._context["asset_profile"] = self._context.get("contract", {}).get("asset_profile", {})
        self._context["asset_template_supplements"] = _load_asset_template_supplements(self._context.get("contract", {}))

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
            key = jf.replace(".json", "")
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        self._context[key] = json.load(f)
                except (json.JSONDecodeError, OSError):
                    self._context[key] = {"_error": "parse_failed"}
            else:
                self._context[key] = {"_missing": True}

        # V12.1: Zone B 薄数据检测 — 文件存在但内容全空 → 视为缺失
        zone_b_keys = ["mda", "segments", "risks", "governance", "audit"]
        for key in zone_b_keys:
            val = self._context.get(key)
            if not isinstance(val, dict) or val.get("_missing") or val.get("_error"):
                continue
            # 检查是否薄数据：所有非 _source 的值都包含 "⚠️ 无提取数据" 或是空数组
            meaningful = False
            for k, v in val.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, list) and len(v) > 0:
                    if not all(isinstance(x, str) and ("⚠️" in x or "无提取" in x) for x in v):
                        meaningful = True
                        break
                elif isinstance(v, dict) and v:
                    meaningful = True
                    break
                elif isinstance(v, str) and v.strip() and "⚠️" not in v and "无提取" not in v:
                    meaningful = True
                    break
            if not meaningful:
                self._context[key] = {"_missing": True, "_thin": True, "_thin_reason": f"{key}.json 内容全空"}

        # V12: 加载定性摘要（如果存在）
        qual_path = os.path.join(data_dir, "qualitative_summary.json")
        if os.path.exists(qual_path):
            try:
                with open(qual_path, encoding="utf-8") as f:
                    self._context["qualitative_summary"] = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        tech_json_path = os.path.join(data_dir, "_technical_snapshot.json")
        if os.path.exists(tech_json_path):
            try:
                with open(tech_json_path, encoding="utf-8") as f:
                    self._context["technical_snapshot"] = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._context["technical_snapshot"] = {"_error": "parse_failed"}
        tech_md_path = os.path.join(data_dir, "_technical_appendix.md")
        if os.path.exists(tech_md_path):
            self._context["technical_appendix_template"] = _load_text_file(tech_md_path)

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
        self._context["tracking_context"] = _build_tracking_context(
            self._config.output_dir,
            self._context.get("contract", {}),
            cb,
        )
        chapters_dir = Path(data_dir) / CHAPTERS_SUBDIR
        if chapters_dir.is_dir():
            for path in sorted(chapters_dir.glob("_ch*.md")):
                match = re.search(r"_ch(\d+)\.md$", path.name)
                if not match:
                    continue
                idx = int(match.group(1))
                self._chapter_memories[idx] = _chapter_memory(_load_text_file(str(path)), idx)
        self._context["identity_ledger"] = _identity_ledger(self._context)
        self._persist_company_memory()

    def _persist_company_memory(self) -> None:
        """Persist deterministic global memory for fresh-context repair passes."""
        if not self._config.output_dir:
            return
        payload = {
            "schema_version": "company-context-memory.v1",
            "identity_ledger": self._context.get("identity_ledger", {}),
            "chapter_memories": {str(k): v for k, v in sorted(self._chapter_memories.items())},
            "policy": "Preserve company facts and cross-chapter reasoning; compact only duplicated payloads.",
        }
        try:
            Path(self._config.output_dir, "company_context_memory.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def _company_memory_block(self) -> str:
        ledger = json.dumps(self._context.get("identity_ledger", {}), ensure_ascii=False, default=str)
        memories = "\n\n".join(self._chapter_memories[idx] for idx in sorted(self._chapter_memories))
        return (
            "## 公司全局记忆（跨章持续保留）\n"
            "以下是公司身份与已完成章节的 thesis-bearing 记忆，不得因上下文优化而丢弃。"
            "后续章节应与其保持事实、口径和叙事连续性；需要原文时再调用 read_chapter。\n\n"
            f"### 指标身份账本\n```json\n{ledger}\n```\n\n"
            f"### 已完成章节记忆\n{memories or '（冷启动，尚无已完成章节；随章节落盘自动积累）'}"
        )

    def _build_resume_hint(self) -> str:
        """检查已有章节文件，生成断点续跑提示。"""
        if self._config.repair_targets:
            completion_path = os.path.join(self._config.output_dir, "completion_report.json")
            findings: list[str] = []
            try:
                with open(completion_path, encoding="utf-8") as handle:
                    completion = json.load(handle)
                target_prefixes = tuple(f"Ch{i}:" for i in self._config.repair_targets)
                findings = [
                    item for item in completion.get("blocking_findings", [])
                    if str(item).startswith(target_prefixes)
                    or str(item).startswith((
                        "Quality:", "Decision:", "Decision reliability:",
                    ))
                ]
            except (OSError, json.JSONDecodeError):
                pass
            target_text = ", ".join(f"Ch{i}" for i in self._config.repair_targets)
            finding_text = "\n".join(f"  - {item}" for item in findings) or "  - 以 audit_chapter 返回为准"
            return f"""
- 🔧 **自动修复轮 {self._config.pass_name}**：只允许修改 {target_text}；其余章节已冻结。
- 本轮完成契约阻断项：
{finding_text}
- 每个目标章先 read_chapter，再按阻断项做最小充分修复；禁止从空白重写或压缩原有内容。
- write_chapter 必须传 force_rewrite=true。单章本轮最多尝试 {self._config.max_chapter_attempts_per_pass} 次；预算耗尽立即转下一目标章。
- E1 只补可靠证据锚点并保留分析深度；P2 扩充实质数据、趋势和推导；S2 先核对 compute_gg 再统一口径。
"""
        import os as _os
        output_dir = self._config.output_dir
        # 章节写入 chapters/ 子目录（write_chapter），旧版曾写在根目录 → 两处都扫，兼容历史产物
        _scan_dir = _os.path.join(output_dir, CHAPTERS_SUBDIR)
        if not _os.path.isdir(_scan_dir):
            _scan_dir = output_dir
        existing = sorted([
            f for f in _os.listdir(_scan_dir)
            if f.startswith("_ch") and f.endswith(".md")
        ])
        if not existing:
            return ""
        chapters_done = [f.replace(".md", "") for f in existing]
        return f"""
- ⚠️ **断点续跑**: 已检测到 {len(existing)} 个已完成章节 ({', '.join(chapters_done[:5])}{'...' if len(chapters_done) > 5 else ''})
- 这些章节如果审计已通过，**不要重写它们**，直接跳过。只写缺失的章节。
- 如果某章审计未通过（文件存在但内容过短），才需要重写。
- 单章本轮最多尝试 {self._config.max_chapter_attempts_per_pass} 次，且短章也计入预算；达到上限后继续下一章。"""

    # ------------------------------------------------------------------
    # System Prompt 构建
    # ------------------------------------------------------------------

    def _build_data_availability(self) -> str:
        """构建数据可用性摘要，让 Agent 明确知道哪些数据可用、哪些缺失。"""
        lines = ["## 数据可用性"]
        lines.append(f"- 数据目录: {self._config.output_dir}")

        # Zone A (定量)
        zone_a_files = {
            "compute_bundle": "定量计算包 (GG/DDM/II)",
            "financial_trends": "财务趋势数据",
            "analysis_contract": "分析合约 (窗口/周期)",
        }
        zone_a_status = []
        for key, label in zone_a_files.items():
            v = self._context.get(key, {})
            if isinstance(v, dict) and v.get("_missing"):
                zone_a_status.append(f"❌ {label} (`{key}.json` 缺失)")
            elif isinstance(v, dict) and v.get("_error"):
                zone_a_status.append(f"⚠️ {label} (`{key}.json` 解析失败)")
            elif v:
                zone_a_status.append(f"✅ {label}")
            else:
                zone_a_status.append(f"❌ {label} (未加载)")
        lines.append("- **Zone A (定量)**: " + " | ".join(zone_a_status))

        # Zone B (定性 — 预提取 JSON)
        zone_b_files = {
            "mda": "管理层讨论与分析",
            "segments": "分部报告",
            "risks": "风险因素",
            "governance": "公司治理",
            "audit": "审计意见",
        }
        zone_b_status = []
        for key, label in zone_b_files.items():
            v = self._context.get(key, {})
            if isinstance(v, dict) and v.get("_thin"):
                zone_b_status.append(f"⚠️ {label} (数据为空)")
            elif isinstance(v, dict) and v.get("_missing"):
                zone_b_status.append(f"❌ {label}")
            elif isinstance(v, dict) and v.get("_error"):
                zone_b_status.append(f"⚠️ {label} (解析失败)")
            elif v:
                zone_b_status.append(f"✅ {label}")
            else:
                zone_b_status.append(f"❌ {label} (未加载)")
        zone_b_any_available = any("✅" in s for s in zone_b_status)
        lines.append("- **Zone B (定性预提取)**: " + " | ".join(zone_b_status))

        # Zone J (判断参数)
        zone_j_files = {
            "moat_assessment": "护城河评估",
            "capex_classification": "资本开支分类",
            "earnings_quality": "盈利质量",
            "data_discount": "数据折价",
        }
        zone_j_status = []
        for key, label in zone_j_files.items():
            v = self._context.get(key, {})
            if isinstance(v, dict) and v.get("_missing"):
                zone_j_status.append(f"❌ {label}")
            elif isinstance(v, dict) and v.get("_error"):
                zone_j_status.append(f"⚠️ {label} (解析失败)")
            elif v:
                zone_j_status.append(f"✅ {label}")
            else:
                zone_j_status.append(f"❌ {label} (未加载)")
        lines.append("- **Zone J (判断参数)**: " + " | ".join(zone_j_status))

        # PDF / page_map 状态
        import os as _os
        data_dir = self._config.output_dir
        pdfs = [f for f in _os.listdir(data_dir) if f.endswith(".pdf") and "年报" in f] if _os.path.isdir(data_dir) else []
        page_maps = [f for f in _os.listdir(data_dir) if f.startswith("page_map") and f.endswith(".json")] if _os.path.isdir(data_dir) else []
        lines.append(f"- **年报 PDF**: {len(pdfs)} 份 ({', '.join(sorted(pdfs)) if pdfs else '无'})")
        lines.append(f"- **Page Map**: {len(page_maps)} 个 ({', '.join(sorted(page_maps)) if page_maps else '无'})")

        # 阅读策略建议
        lines.append("")
        if not zone_b_any_available:
            lines.append("**⚠️ Zone B 定性数据全部不可用**。所有定性信息需通过 `read_section` 直接从年报 PDF 提取。")
            lines.append("每章写作前，请用 `read_section` 阅读至少近 3 年对应章节，优先使用有 page_map 的年份（快速随机访问）。")
        else:
            lines.append("**读取策略**: `read_zone_data` 用于快速定位，但数据丰富档不得停在摘要层；核心论点必须再用 `read_section`/`search_report` 回到年报原文核验。")

        return "\n".join(lines)

    def _judgment_task_context(self) -> dict[str, Any]:
        try:
            from scripts.judgment_research_resume import next_judgment_research_pass
        except ModuleNotFoundError:
            from judgment_research_resume import next_judgment_research_pass
        context = next_judgment_research_pass(self._config.output_dir)
        if not context or context.get("task_id") != self._config.judgment_task_id:
            raise RuntimeError(
                f"定向研究断点与请求任务不一致: requested={self._config.judgment_task_id}"
            )
        return context

    def _judgment_task_state(self) -> dict[str, Any]:
        path = Path(self._config.output_dir) / "judgment_research_execution.json"
        try:
            ledger = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"state": "NOT_STARTED", "task_status": "MISSING", "violations": []}
        entry = ((ledger.get("tasks") or {}).get(self._config.judgment_task_id) or {})
        return {
            "state": ledger.get("state"),
            "active_task_id": ledger.get("active_task_id"),
            "task_status": entry.get("status"),
            "violations": list(entry.get("violations") or []),
        }

    def _judgment_task_finished(self) -> bool:
        return self._judgment_task_state().get("task_status") in {"COMPLETE", "VIOLATION"}

    def _build_judgment_task_system_prompt(self) -> str:
        """Build a compact, task-only prompt for a genuinely fresh context."""
        context = self._judgment_task_context()
        task = context["task"]
        supporting: dict[str, Any] = {}
        try:
            review = json.loads(
                Path(self._config.output_dir, "judgment_review.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            review = {}
        if isinstance(review, dict):
            supporting["judgment_review"] = {
                key: review.get(key) for key in (
                    "ceiling_verdict", "verdict_basis", "distinctive_insight",
                    "competitive_explanation_test", "decision_dependency",
                ) if review.get(key) not in (None, "", [], {})
            }
        try:
            insight = json.loads(
                Path(self._config.output_dir, "insight_ledger.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            insight = {}
        insight_id = str((review.get("distinctive_insight") or {}).get("insight_id") or "")
        matching = next((
            item for item in insight.get("insights") or []
            if isinstance(item, dict) and str(item.get("insight_id") or "") == insight_id
        ), None) if isinstance(insight, dict) else None
        if matching:
            supporting["decisive_insight"] = matching
        allowed = set(context.get("allowed_tools") or [])
        tool_list = "\n".join(
            f"- {item['function']['name']}: {item['function']['description']}"
            for item in self._tools.get_schemas()
            if item.get("function", {}).get("name") in allowed
        )
        resume_instruction = (
            "任务已是ACTIVE断点：禁止再次调用begin；只执行remaining_required_tools，"
            "不得重复已经成功的来源调用。"
            if context.get("resume") else
            "任务尚未开始：第一步调用begin_judgment_research_task，且task_id必须完全一致。"
        )
        return f"""你是价值投资框架中的单任务研究执行器，不是全文报告写作者。

{_judgment_first_prompt_block("research")}

## 唯一任务
{json.dumps(task, ensure_ascii=False, indent=2)}

## 可恢复执行状态
{json.dumps({key: context.get(key) for key in ('task_id', 'resume', 'successful_tools', 'attempted_tools', 'remaining_required_tools', 'unattempted_required_tools', 'remaining_tool_calls', 'completion_repair')}, ensure_ascii=False, indent=2)}

{resume_instruction}

## 相关判断上下文（仅用于理解缺口，不得当作外部证据）
{json.dumps(supporting, ensure_ascii=False, indent=2)}

## 执行纪律
- 每次只处理上述任务；不得加载或重写整份报告。
- 严格遵守maximum tool calls与mutation_scope。只有新证据改变主张时才写允许的章节/账本。
- 8次上限只约束证据获取工具；取证结束后仍可读取允许章节/合同并做有限写回。若chapter_update.needed=true，必须先实际写回声明章节再complete；若无需改正文则设false且chapters=[]。
- read/search的结果必须真的支持主张；“未找到”只能记为PUBLIC_INFO_UNAVAILABLE，不能变成正面证据。
- outcome必须是EVIDENCE_FOUND、PUBLIC_INFO_UNAVAILABLE、NO_DECISION_CHANGE或DECISION_CHANGED之一。
- source_ids写可复核的文件、页码、URL或工具返回身份。
- 每个来源工具结果都附带`judgment_research_meta.source_id`和`evidence_usable`；complete的source_ids与
  finding.evidence_items[].source_id必须逐字使用这些机器ID。禁止自行发明或拼接source_id。
- 若可恢复状态含`completion_repair.last_submission_errors`，必须以`previous_finding`为底稿逐项修正；只允许使用`usable_sources`列出的机器ID，并使chapter_update与`actual_changes`完全一致。不得丢弃错误信息后重新猜测。
- complete中的finding必须完整填写：schema_version=`judgment-research-finding.v1`、task_id、resolution
  （SUPPORTED/CONTRADICTED/MIXED/UNRESOLVED/PUBLIC_INFO_UNAVAILABLE）、prior_claim、evidence_items
  （source_id/source_kind=primary_filing|official_data|independent_dataset|company_statement|secondary_research|market_data|unknown、
  directness=DIRECT|INDIRECT|CONTEXT、relation=supports|contradicts|context、fact/as_of）、strongest_alternative、discriminating_result、inference、
  applicability_conditions、confidence_update（before/after/basis；可用0-1数字，也可用有依据的定性描述，禁止为了过门编造概率）、valuation_impact与action_impact
  （state=NONE/CHANGED/UNCERTAIN、basis、changes）、chapter_update（needed/chapters/reason）。
- “有新事实但不改变决策”用EVIDENCE_FOUND且影响state=NONE；NO_DECISION_CHANGE表示核验后没有新增的决策相关证据。
- PUBLIC_INFO_UNAVAILABLE要求所有required_tools至少真实尝试一次；失败或空结果不算成功证据，但允许作为“已检索仍不可得”的停止依据。
- 最后必须调用complete_judgment_research_task；结构化finding不完整时执行账本会标记VIOLATION。
- 禁止调用assemble_report；报告只由外层运行器在全部任务结束后统一装配。

## 本任务可见工具
{tool_list}
"""

    def _judgment_tool_schemas(self) -> list[dict[str, Any]]:
        context = self._judgment_task_context()
        allowed = set(context.get("allowed_tools") or [])
        remaining = int(context.get("remaining_tool_calls") or 0)
        unattempted = set(context.get("unattempted_required_tools") or [])
        source_tools = {
            "search_report", "read_section", "web_search", "web_fetch",
            "get_peer_comparison", "get_market_data", "get_financial_statement",
            "get_financial_trends", "read_zone_data",
        }
        if remaining <= 0:
            allowed = (allowed - source_tools) | {"complete_judgment_research_task"}
        elif unattempted and remaining <= len(unattempted):
            allowed = (allowed - source_tools) | unattempted | {"complete_judgment_research_task"}
        return [
            item for item in self._tools.get_schemas()
            if item.get("function", {}).get("name") in allowed
        ]

    def _load_judgment_synthesis(self) -> dict[str, Any]:
        try:
            value = json.loads(
                Path(self._config.output_dir, "judgment_research_synthesis.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _judgment_synthesis_finished(self) -> bool:
        return self._load_judgment_synthesis().get("state") == "REVIEWED"

    def _build_judgment_synthesis_system_prompt(self) -> str:
        synthesis = self._load_judgment_synthesis()
        if synthesis.get("state") != "AWAITING_INDEPENDENT_REVIEW":
            raise RuntimeError(
                f"定向研究综合状态不可复核: {synthesis.get('state') or 'MISSING'}"
            )
        context: dict[str, Any] = {"research_synthesis": synthesis}
        for filename in (
            "judgment_review.json", "insight_ledger.json", "claim_evidence.json",
            "decision_ledger.json", "valuation_model.json",
        ):
            try:
                value = json.loads(Path(self._config.output_dir, filename).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if filename == "claim_evidence.json":
                value = {"claims": [
                    {key: item.get(key) for key in ("claim_id", "claim", "confidence", "decision_impact", "decision_entry_ids")}
                    for item in value.get("claims") or [] if isinstance(item, dict)
                ]}
            elif filename == "decision_ledger.json":
                value = {"entries": [
                    {key: item.get(key) for key in ("entry_id", "metric", "value", "unit", "status")}
                    for item in value.get("entries") or [] if isinstance(item, dict)
                ]}
            elif filename == "valuation_model.json":
                value = {"models": [
                    {key: item.get(key) for key in ("model_id", "name", "status")}
                    for item in value.get("models") or [] if isinstance(item, dict)
                ], "synthesis": value.get("synthesis")}
            context[filename] = value
        return f"""你是独立判断复核员。研究任务已由其他上下文完成；你不能搜索、补证据或改报告。

{_judgment_first_prompt_block("synthesis")}

## 复核材料
{json.dumps(context, ensure_ascii=False, indent=2)}

## 工作要求
- 逐项判断finding是否真正解决原缺口，而不是把“找到材料”等同于“支持主张”。
- 明确最强替代解释是否被区分；MIXED/UNRESOLVED不得包装成确定结论。
- 判断证据是否改变置信度、估值参数或动作；没有传导时明确说明为什么没有。
- 保留仍成立的旧评审内容，只根据finding更新已解决/仍脆弱部分。
- ceiling_verdict可以升、降或不变；理由必须指向任务finding，不能因新增来源数量自动升级。
- 只调用一次finalize_judgment_research_review，原子提交完整judgment_review和综合结论；
  integrated_task_ids必须覆盖全部task_findings。remaining_gaps会由工具层自动同步到missing_information，
  不需要为了逐字复制缺口进行第二次提交。
- 禁止调用任何搜索、写章、决策账本、估值账本或assemble工具。
"""

    def _judgment_synthesis_tool_schemas(self) -> list[dict[str, Any]]:
        allowed = {"finalize_judgment_research_review"}
        return [
            item for item in self._tools.get_schemas()
            if item.get("function", {}).get("name") in allowed
        ]

    def _build_system_prompt(self) -> str:
        """构建 Agent system prompt。V12 模式自动检测。"""
        contract = self._context.get("contract", {})
        effective_years = contract.get("effective_years", [])
        cycle_type = contract.get("cycle_type", "未知")
        analysis_start = contract.get("analysis_start_year", "?")

        tool_list = "\n".join(
            f"- **{t['function']['name']}**: {t['function']['description']}"
            for t in self._tool_schemas_for_stage()
        )

        company = self._context.get("company_name", self._config.code)
        asset_profile = self._context.get("asset_profile", {})
        template_supplements = self._context.get("asset_template_supplements", [])
        technical_snapshot = self._context.get("technical_snapshot", {})
        technical_appendix_template = self._context.get("technical_appendix_template", "")
        full_template_raw = self._context.get("template_raw", "")
        is_v12 = "Part A" in full_template_raw and "定性深度分析" in full_template_raw
        try:
            from scripts.chapter_depth import detect_data_richness, semantic_depth_prompt
        except ModuleNotFoundError:
            from chapter_depth import detect_data_richness, semantic_depth_prompt
        depth_contract_block = semantic_depth_prompt(
            data_rich=detect_data_richness(self._config.output_dir)
        )
        template_raw = full_template_raw
        if self._config.repair_targets:
            targeted_template = _template_sections_for_targets(
                full_template_raw,
                self._config.repair_targets,
            )
            if targeted_template:
                template_raw = targeted_template
            # 资产补充模板用于首轮完整建模；修复轮只看目标章节合约。
            template_supplements = []
        # Stage 5: the full template is mechanical framework context, not company
        # knowledge. Keep only a map in the repeated prefix; disclose each complete
        # contract immediately before writing that chapter.
        template_raw = _compact_template_index(full_template_raw)
        version = "V12" if is_v12 else "V11"

        tracking_context = self._context.get("tracking_context")
        tracking_context_text = _format_tracking_context(tracking_context)
        tracking_context_block = ("\n" + tracking_context_text + "\n") if tracking_context_text else ""

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
        if is_v12 and not self._config.repair_targets:
            v12_methodology = """
## V12 Dayu 定性分析方法论

本报告采用 Dayu 定性深度分析 + Turtle 定量估值的统一框架。

### 证据引用格式（V12.18 简化）

- 数据断言后加 `[source: 文件 数据]`，格式任意。组装报告时自动提取为文末脚注 + _sources.json
- 一个段落/一个 bullet 放一个合引用即可，不需要逐句加
- web_search 来源保留内联：`[source: web_search → {域名}]`

### 定性写作规范（Part A Ch1-Ch9）— 来自 Dayu write_chapter.md

**结构要求**：
- 每章必须包含三部分：**结论要点** / **详细情况** / **证据与出处**
- **章节大标题必须用 `## `（h2）**——这是 HTML TOC 侧栏的唯一锚点。如 `## Ch1 公司做的是什么生意`
- 结论要点用 `### 结论要点`（h3），bullet 简明扼要
- **「详细情况」用 `#### ` 四级标题分隔为子节**（如 `#### 核心产品与服务`）。禁止连续段落堆砌。

**段落写作规范（强制）**：
- ⛔ **严禁"一句一段"的笔记体写法**。相关句子必须合并在同一自然段落内，用句号分隔。
- 自然段落由 2-5 个相关句子组成——只有当话题确实切换时才用空行换段。
- 一个段落的句子之间**不留空行**——空行 = 段落分隔符，意味着"新话题开始"。
- 自检：写完一章后，若发现连续出现 3 个以上的单句段落，必须合并重写。

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
- 本章末尾必须包含 `### 证据与出处` 小节（表格列出所有来源及关键数据）
- ⛔ **禁止逐句 `[source]`**——如果发现每句话后面都有一个 `[source]`，必须重写整章
- **引用放在每段/每 bullet 末尾**，一段一个合引用，合并所有来源
- 引用格式人类可读，不要字段路径：
  ✅ `[source: mda.json FY2025 营收=220.7亿(+2.7%), ROE=13.5%]`
  ❌ `[source: mda.json → mda_key_financials → 2025]`
- GG/DDM 等定量结果必须展示**完整计算链路**：每个参数来源 + 计算步骤 + 最终值

**读者指南（报告开头自动生成）**：
- 3 分钟读者 → 投资要点概览 + 综合决策
- 15 分钟读者 → 加 Ch1-Ch4（生意+行业+护城河+变化）+ Ch11-Ch12（GG+内在价值裁决）
- 验算读者 → 各章"证据与出处"定位到具体 JSON 字段/年报页码

**深度要求**：
- 有同行数据时用对比表，有财务数据时用趋势表。没有数据时不做机械填充。
- GG 计算注意：compute_bundle 中的市值可能因 yfinance 股本数据错误而偏小，请用 373.5M 股 × 最新股价 验证市值

### Facet 系统
模板中的 COMPANY_FACET_CATALOG 包含 36 种业务类型 + 25 种约束条件。
写作前先根据 financial_trends.json 和 segments.json 判断公司的主业务类型和关键约束，
然后在章节中优先使用匹配的 preferred_lens（认知口径）。

### 关键输入成本敏感性（通用规则，非写死某个行业）
在 Ch11 GG 和 Ch13 DDM 中，检查公司是否存在 **由外部方定价的关键输入品**：
- 特许经营/品牌授权 → 浓缩液/特许权使用费由品牌方定价
- 大宗商品依赖 → 原材料（白糖/原油/金属）价格由市场决定
- 单一供应商集中 → 关键零部件或原料的定价权在供应商手中
- 监管定价 → 产品价格受政府管制

若发现上述模式，**必须对关键输入品提价 5%/10%/15% 做敏感性分析**，量化对毛利率和 GG 的冲击。每条情景必须附带 **概率估计**（高/中/低 + 百分比区间），并说明概率判断的依据（历史频率、合同条款、行业惯例）。格式："提价5%概率中(30-40%)——过去10年可口可乐每3-4年提价一次；提价15%概率低(<10%)——会触发装瓶商联合抵制"。这是通用的"外部依赖风险"量化框架，不限于某个特定行业。

### 四大师交叉验证（V12.20 吸收自 ai-berkshire）

每份报告的 Ch3、Ch8、Ch14 必须包含以下四个视角的交叉验证段落：

**段永平视角 — 生意本质（Ch3 护城河）**
- 必须回答："如果只能用一句话描述这门生意的护城河，是什么？"
- 追问：这门生意10年后还存在吗？用户为什么离不开它？
- 用毛利率/ROE 行业分位支撑，但本质判断必须是定性的

**芒格视角 — 逆向思考（Ch8 风险）**
- 必须包含一段芒格式逆向："聪明人为什么不买这家公司？"
- 列出至少 3 条反方最有力的论点，逐条回应
- 最危险的偏见是什么？（确认偏误、近因偏误、锚定偏误）

**段永平+巴菲特 — 管理层镜子测试（Ch8 治理）**
- CEO 过去 5 年的资本配置决策复盘
- 如果只能用 5 句话向一个不懂这行的人解释你为什么持有这家公司，你能说清楚吗？
- 说不清楚 → 仓位打五折

**段永平 — 5 年持有测试（Ch14 决策）**
- 必须回答："如果股市明天关闭 5 年，你愿意以当前价格持有这家公司吗？"
- 如果答案是"不确定" → 决策降一级（Buy→Hold, Hold→Pause）
- 如果答案是"不愿意" → 直接 Avoid

### 估值方法选择矩阵（V12.20 吸收自 stock-analytics-skill）

不要在 Ch10/Ch11 机械套用所有估值方法。必须根据公司特征选择，并说明理由：

| 公司类型 | 首选方法 | 次选 | 不适合 |
|---------|---------|------|--------|
| 稳定消费品（茅台/飞鹤） | PE + DDM | DCF | PB（轻资产不适用） |
| 周期制造（海螺/紫金） | PB + EV/EBITDA | 正常化PE | DDM（分红不稳定） |
| 银行/保险 | PB + ROE-COE | 股利贴现 | DCF（杠杆不适用） |
| 高成长（腾讯/美团早期） | PEG + 反向DCF | PS | PE（亏损期不适用） |
| 物业/REIT | DDM + P/FFO | PB | PE（折旧扭曲利润） |

**上表选的是「展示口径」（PE/DDM/PB）。真正的估值模型由综合派六路由决定——先定路由再选口径**：
- R1 困境清算 → IV=AV_liq（清算价值），展示口径 PB
- R2 重置/进入 → IV=AV_going（重置价值），展示口径 PB + EV/EBITDA
- R3 稳定无增长 → IV=EPV（=正常化盈利/r*），展示口径 正常化PE
- R4 价值毁灭 → IV=min(AV×折价, EPV)，展示口径 PB
- R5 特许经营（护城河可验证）→ IV=EPV+增长价值，展示口径 PE/DDM + 回报分解
- R6 多业务 → SOTP 分部估值
λ 兑现折算只作用于 R3/R5。详见方法论「综合派估值与回报框架」节。

**Ch10 估值章第一条必须是方法选择理由**，格式："本公司属于路由 [Rx][理由]，故 IV 主估值采用 [EPV/AV/EPV+增长]。展示口径选 [方法A] 和 [方法B]，因为 [公司特征]。不采用 [方法C] 因为 [原因]。"

### 可比公司分析增强（V12.20）

同行对比表必须增加"调整系数"列：
- **增长差异调整**：目标公司 3y 营收 CAGR vs 同行中位数 → 每 5pp 差异调整 PE 10%
- **风险差异调整**：目标公司负债率 vs 同行中位数 → 每 10pp 差异调整 PE 5%
- **盈利差异调整**：目标公司 ROE vs 同行中位数 → 每 5pp 差异调整 PE 10%

格式：`调整后合理PE = 同行中位PE × (1 + 增长调整 + 风险调整 + 盈利调整)`

### 行业对比分析框架（V12.17 强化）

行业对比数据服务于"判断分岔点"，不是在 Ch2 放一张排名表就算完事：
- **关键问题**：公司跟行业中位数的差异来自哪里？可持续吗？
- **毛利率高于行业中位数** → Ch3 护城河里追问：溢价能力还是成本结构优势？
- **ROE 高于行业中位数** → Ch6 财务表现里追问：高杠杆驱动还是高利润率驱动？杜邦拆解
- **营收增速落后行业** → Ch4 近期变化里追问：市场份额流失还是主动收缩？
- **OCF/NP 与行业背离** → Ch6 追问：盈利质量差异还是营运资本管理不同？

**行业对比必须跨章联动**：
- Ch2（行业位置）：行业关键竞争变量 + 公司在变量上的位置
- Ch3（护城河）：用 ROE/毛利率的行业分位支撑护城河证据
- Ch5（经营表现）：用营收增速/周转率分位判断经营效率
- Ch6（财务表现）：用资产负债率/OCF_NP 分位判断财务健康度
- Ch12（DDM估值）：用 PE/PB 分位判断估值折价来源

**禁止**：
- "毛利率 P57，处于行业中等水平" — 没有任何判断价值
- 只列排名不解释差异原因
- 把行业对比数据只放在 Ch2，不在 Ch3/Ch5/Ch6 引用
- 因为同行数据缺失就跳过对比（至少做国内同行 × 基本指标）

### 国际对标分析（V12.15 新增）
当公司有全球可比同行时（如装瓶商 vs CCEP/太古可口可乐），必须在 Ch2 中做国际对标：
- 写 Ch2 前调用 `get_global_benchmarks` 获取国际对标搜索方案
- 用 `web_search` 按 search_queries 获取实时财务数据
- 构建 ≥3 家国际同行 × ≥4 项指标的对比表
- 分析框架：差异来源 → 商业模式差异 vs 竞争劣势 vs 市场环境
- 派息率差距是重点——如果国际同行派息率显著更高，可能是管理层资本配置效率低下的证据

### 已定价风险 vs 永久性资本毁灭（V12.18 新增）

当治理章讨论"接班人风险""强人依赖""关键人物风险"时，必须区分两类风险：

| 已定价风险（估值折价） | 永久性资本毁灭（否决） |
|---|---|
| 市场已知，PE/PB 已大幅低于行业 | 可能摧毁生意本身（欺诈、牌照吊销） |
| 存在反向期权价值（如退休后市场化改革） | 不存在改善情景 |
| → 体现为仓位折扣，不构成否决 | → 构成否决 |

讨论"接班人未定"时，必须同时回答：
1. 市场是否已对此定价？（PE/PB vs 行业 vs 历史分位）
2. 若已定价，"退休后可能推行的改革"的正面期权价值是什么？
3. 此风险是估值折价还是资本毁灭？— 前者仓位打折，后者直接否决。

### 少数股东治理张力分析框架（V12.15 新增）
当公司存在显著少数股东（parent_ratio < 0.90）且少数股东具有双重身份时，必须进行治理张力分析：
- **识别信号**：parent_ratio < 0.90 / dual_role_shareholders 非空 / 关联交易占比 >10%
- **分析维度**：
  1. 利润上移能力：少数股东是否限制了利润上移和分红决策？
  2. 分红决策权：如果少数股东不同意提高派息率，控股股东能否单方面提高？
  3. 利益冲突：少数股东的双重身份（如供应浓缩液+持股35%）在利润分配中是否存在利益冲突？
  4. 历史行为：过去5年有无释放股东价值的先例？有无关联交易定价争议？
- **估值影响**：
  - 治理折价是结构性（永久）→ GG 折价应当永久化，不作为可改善的"期权价值"
  - 治理折价可改善（如合资协议到期可重新谈判）→ 标注为期权价值 + 改善时间窗口
- **跨章联动**：
  - Ch8（治理）→ 定性分析治理张力，回答三个核心问题
  - Ch11（GG）→ 引用 governance_tension.json，展示治理折价对 GG 的定量影响
  - Ch14（决策）→ 治理张力作为决策降级因素，如果定量说 Buy 但治理张力=high，考虑降为 Hold

### 创新业务 / 多业务线估值处理
若 segment_data 或 mda 中存在增速显著高于传统主业的新业务线（如数字营销平台、智慧零售、D2C等），注意：
- 新业务的增长逻辑、风险特征、资本需求通常与传统装瓶/制造业务完全不同
- **不要**把新业务的高增速简单揉进 g_base（会高估传统业务终值）
- 在 Ch11 GG 和 Ch13 DDM 中，对创新业务赋予保守假设（增长率降为传统业务水平，或单独做 SOTP 给 0 终值），并说明理由

### Web 搜索使用规则
你有 **web_search** 和 **web_fetch** 工具，可用于补充 DB/年报中不可用的信息：
- web_search(query): 搜索网络，返回标题+URL+摘要（免费，无需 API key）
- web_fetch(url): 抓取某篇文章的详细内容

**何时用**：行业新闻/竞争动态/公司最新事件/监管披露——这些 DB 和年报里没有。
**何时不用**：财务数据/股价/分红——这些 DB 里已有，不要浪费 token。

**网络数据可信度低于年报数据**，使用时必须遵守：

**数据可信度层级**（高→低）：
1. `stock_analysis.db`（经审计的财务数据）— 最高可信度
2. PDF 年报原文（公司官方披露）— 高可信度
3. Zone B JSON（LLM 预提取）— 中高可信度，需交叉验证
4. Web 搜索（第三方网站/新闻）— **低可信度，仅用于补充**

**使用条件**：
- 仅当 Zone B + DB + PDF 都无法提供某个数据时才使用 web 搜索
- 典型用途：行业新闻（管理层变动、并购传闻）、同行对比数据（竞品毛利率）、品牌估值/市占率第三方估算
- **禁止**用 web 搜索结果覆盖 DB 或年报数据——若冲突，以 DB/年报为准

**引用格式**：网络数据必须标注 `[source: web_search → {域名} {日期}]`，不能与年报来源混用

### 定性→定量桥接
完成 Part A 全部 9 章并审计通过后：
1. 读取所有定性章节，提取 qualitative_summary.json（包含 moat_rating, moat_sources, b_penalty_evidence, g_base_context, earnings_quality, data_discount_signals, veto_level_risks 等关键字段）
2. 这些字段将用于增强 Zone J 参数估计（moat/capex/earnings_quality/data_quality）

### 统一决策合成 — 来自 Dayu write_research_decision.md

## 分析基调
默认**保守偏空**——对乐观解释要求更高的证据标准，对悲观情景赋予更重的权重。

### 资产陷阱三段论（净现金/MC>50% 时强制执行）
当公司净现金占市值比例高时，必须回答三个问题：
1. **现金在谁手里**：控股股东/公司账上/中小股东可及？若存放于集团财务公司或境外子公司，可及性存疑。
2. **催化剂在哪里**：有无特别分红/大额回购/资产剥离计划？若无，便宜可能长期维持。
3. **历史验证**：过去5年有无释放股东价值的先例？若从未发生，不应假设"这次会不同"。

**决策优先级规则（V12.18 更新）**：
- 当定性决定与定量决定冲突时，**定量决定（GG/DDM/否决门）为第一优先**
- 定性决定只能调整仓位（Continue→仓位加满，Pause→仓位减半），不能在定量否决时"拉回"决策
- **例外（V12.18 逆向覆盖）**：若 compute_bundle 中 `contrarian_override.active=true`，说明定量 Avoid 仅因一次性扰动（S2 扰动豁免）触发，且 PE 已极度压缩（<12x）。此时 Agent 应在 Ch14 中讨论逆向机会——市场对已知风险的过度定价本身构成安全边际，决策可升级为 Cautious Watch（1-2%仓位）
- **例外（V12.18 定性降级）**：若定量=STRONG_BUY 但定性=Pause（待验证的结构性问题未解决，如国企治理、小票流动性、客户集中等），Agent 必须在 Ch14 中将 STRONG_BUY 降级为 BUY，仓位从满仓降至 1-2%。理由：定量便宜但定性风险未释放时，重仓不理性。格式："定量指标显示 Strong Buy，但由于[X/Y/Z]定性问题尚未验证，降级为 Buy，仓位控制在 2%以内。"
- **定性"Continue/Pause边界"处理**：若 Agent 自评定性处于 Continue 和 Pause 的边界（如"偏 Pause 的 Continue"），在决策矩阵中应将其计为 Pause，不能模糊处理。边界状态意味着部分关键判断仍有待验证，取保守侧。
- 禁止"取折中"——如果定量说 Avoid 且无 contrarian_override，最终必须是 Avoid 或 Strong Reject，不能变成 Hold

Part C 的 Ch14 综合决策使用 5 状态合成矩阵。写 Ch14 前必须检查：
- `compute_bundle.factor3.minority_adjustment` → 如存在，安全边际必须按归母 AA 重新评估
- `compute_bundle.factor3.aa_avg.3y` → 确认是真 AA 还是已调整 AA
- 若 Zone J 文件缺失且 `total_discount_pct=0`，必须在"数据完整性"小节中**显式计算**折价15%后的 GG 和 DDM，不能只提建议不执行

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
            # 注入综合派估值框架（canonical 单一真相源）。
            # 缺失时 _load_graham_framework 返回空串，回退到模板自带 GG/DDM 纪律。
            v12_methodology += _load_graham_framework()
        elif is_v12:
            targets = set(self._config.repair_targets)
            v12_methodology = """
## 自动质量修复方法（精简上下文）

- 只修 completion contract 指定章节，先读取旧章和 audit 结果，保留已正确的分析与表格。
- P2：增加实质数据、跨年趋势、对比与推导，不用一句一段或空行凑行数。
- E1：核对原始工具结果，在相关段落或 bullet 末尾补 `[source: 文件/工具 关键字段=值]`；禁止虚构来源。
- S2：区分 AA GG、FCFE GG、Normalized GG，不把不同口径强行统一成一个值。
- 每章包含结论、详细情况、证据与出处；修完立即 audit，预算耗尽就转下一目标章。
"""
            if targets.intersection({10, 11, 12, 13, 14}):
                v12_methodology += """

### 量化修复纪律

- 先调用 compute_data_quality、get_market_data、compute_aa、compute_gg、compute_ddm，禁止凭记忆改数字。
- Ch11 展示 AA/FCFE/Normalized 三种 GG 身份、参数、公式、情景、HH、敏感性、压力测试、AP、少数股东、λ和治理折价。
- Ch12 完成六路由→IV(r*)→分红率→V_cash(r*)→λ五档→V_final→回报安全边际，不能用净资产一坨替代 AV bridge。
- Ch13 明确 DDM 是永续分红上限参考，并与 P_base/P_FCFE/V_final 和目标回报门槛价交叉验证。
- Ch14 在核心章节修复后最后更新；Ch0 必须最后更新，确保决策和指标一致。
"""
            if targets.intersection({11, 12, 13}):
                v12_methodology += """

### 综合派框架按需读取

- 修复轮不重复注入整套综合派全文。先保留旧章中已经正确的框架链路，只针对 audit 缺口补强。
- 需要执行细则时调用 `read_framework_reference`：Ch12 优先 `asset_value`、`epv`、`routing`、`growth`、`incremental_growth`、`cost_of_capital`；Ch13 的回报分解用 `r5_return`。
- 工具返回的 canonical 文档是单一真相源；不得凭记忆简化公式或改变 λ、AV、EPV、R5 定义。
"""

        # 构建数据可用性摘要
        data_availability = self._build_data_availability()

        # 根据 Zone B 数据可用性调整分析方法论步骤 2
        zone_b_available = any(
            not (isinstance(self._context.get(z), dict) and self._context[z].get("_missing"))
            for z in ["mda", "segments", "risks", "governance", "audit"]
        )
        if zone_b_available:
            zone_methodology = """2. **读取 Zone B 洞察（优先）**: 调用 read_zone_data(mda/segments/risks/governance/audit)
   这些 JSON 已提炼关键结论+数据+证据引用，信息密度远高于原始 PDF。
   若某 zone 不存在，再用 read_section 读原始 PDF 补充。
   ⚠️ **即使 read_zone_data 成功返回，也要检查返回数据中是否包含 "⚠️ 无提取数据" 标记**。
   若某个关键字段（如 auditor_history、related_party_transactions）标记为 "⚠️ 无提取数据"，
   必须用 read_section 针对性补充——不要接受空数据。"""
            qual_chapter_prep = "- 定性章(Ch1-Ch9): 先调 **get_peer_comparison** + get_financial_trends + read_zone_data 刷新上下文"
        else:
            zone_methodology = """2. **读取年报PDF**: Zone B 预提取数据不可用。直接调用 read_section(section=MDA/SEG/GOV/AUDIT/RISK)
   读取各年份年报对应章节。每章写作前，至少阅读近3年的相关章节。
   先用 list_documents 确认哪些年份有 page_map（快速随机访问）vs 需全量扫描。"""
            qual_chapter_prep = "- 定性章(Ch1-Ch9): 先调 **get_peer_comparison** + get_financial_trends + **read_section** 刷新上下文（Zone B 不可用，直接用 read_section 读年报原文）"

        asset_profile_block = ""
        if asset_profile:
            asset_profile_block = f"""
## 资产类型识别
- asset_type: {asset_profile.get('asset_type', 'stock')}
- analysis_mode: {asset_profile.get('analysis_mode', 'stock')}
- notes: {' | '.join(asset_profile.get('notes', []) or [])}
"""

        supplement_block = ""
        if template_supplements:
            parts = []
            for item in template_supplements:
                content = (item.get('content') or '').strip()
                if content:
                    parts.append(f"### {item.get('name')}\n{content}")
            if parts:
                supplement_block = "\n## 资产专项补充模板\n" + "\n\n".join(parts)

        technical_block = ""
        if isinstance(technical_snapshot, dict) and technical_snapshot and not technical_snapshot.get('_error'):
            signal_keys = ', '.join((technical_snapshot.get('signals') or {}).keys())
            technical_block = f"""
## 技术分析快照
- 已生成 `_technical_snapshot.json`，可用信号：{signal_keys or 'none'}
- 若报告包含技术附录，必须直接引用 `_technical_snapshot.json` 与 `_technical_appendix.md`，不能自行虚构技术指标。
- 技术面只可作为附录或辅助判断，不能覆盖基本面主结论。
"""
        company_memory_block = self._company_memory_block()
        try:
            from scripts.reader_coverage import reader_coverage_prompt
        except ModuleNotFoundError:
            from reader_coverage import reader_coverage_prompt
        reader_coverage_block = "\n## 读者层覆盖契约\n" + reader_coverage_prompt()

        return f"""# 龟龟策略分析师 ({version})

你是龟龟投资策略的**唯一分析师**。你拥有完整的分析上下文和工具集。
按顺序逐步完成分析，主动调用工具获取所需数据。

{_judgment_first_prompt_block("report")}

## 分析标的
- 代码: {self._config.code}
- 公司: {company}
- 数据目录: {self._config.output_dir}
- 周期分类: {cycle_type}
- 有效分析窗口: {effective_years}（起始: {analysis_start}）
{self._build_resume_hint()}
{data_availability}
{asset_profile_block}
{technical_block}
{qual_context_block}
{tracking_context_block}{v12_methodology}
{supplement_block}
{company_memory_block}
{reader_coverage_block}
## 分析方法论
1. **了解数据**: 调用 list_documents 查看可用文档
2. **读取判断生成上下文与官方证据**: 以 read_report_contract_pack 中的 `judgment_generation_handoff` 为统一入口；上下文变化时可调用 read_judgment_generation_handoff 刷新受控视图。先用 RESEARCH_AGENDA 限定官方证据范围、1-3个决定性问题、行业验证提示和候选方法提示；若合同包提供 INVESTMENT_ENRICHMENT，再继承同cutoff且G1-J完整的公司判断前置物。READY_WITH_NO_PRIOR只表示可从官方证据继续，不表示判断已经冻结。随后调用read_evidence_context回读VERIFIED事实和observation_id；旧的read_valuation_route、read_industry_knowledge_context和read_decisive_question_plan保留为明细读取接口。行业机制只能提出问题、反例和取证清单，候选方法提示也不能成为公司事实、旧结果、估值参数、概率、价格或行动依据。search_report命中只属于CANDIDATE；未自动抽取的关键事实必须用read_section按页回读，再调用verify_official_fact逐字验证。未找到不得推断为不存在、规模很小或已经定价。基准率只能引用对应机制查询中的ELIGIBLE `CASE:`记录；少于5个合格案例时不得输出经验概率，130家估值模型只可帮助选择机制/模型，不是历史结果证据。逐项完成有界研究后必须调用write_decisive_question_findings，记录区分信号、解释更新及估值/动作变化；INCONCLUSIVE或PUBLIC_INFO_UNAVAILABLE也必须记录尝试来源且不得提高置信度。报告必须围绕入选question_id，不得另造自由问题
{zone_methodology}
3. **提取财务**: 调用 get_financial_statement 和 get_financial_trends 获取定量数据
4. **定量计算**: 调用 compute_gg、compute_ddm、assess_moat 完成估值
5. **写作报告**: 本轮开始一次调用 read_report_contract_pack，并先处理其中判断handoff的readiness/findings；随后按合同包逐章 write_chapter，写完后审计（audit_chapter）
   - **Ch0 投资要点概览**：最后写（chapter_index=0），总结全部 14 章的核心发现
   - 其他章节 chapter_index 与模板序号一致（Ch12=内在价值合成与裁决，Ch13=DDM估值与仓位执行，Ch14=综合决策）
6. **最终决策**: 综合各因子给出最终结论
7. **固化决策身份**: 调用 write_decision_manifest，将定性/定量判断、展示标签和仓位写入唯一真源
   - **账本分阶段提交纪律**：写 claim/valuation/financial_driver/thesis/decisive/insight/judgment 中任一结构化产物前，必须先调用 `read_structured_ledger_contract(ledger=...)` 读取精确嵌套类型与当前可用 ID。若对应 ledger 尚不存在，先以 `freeze=false` 提交完整结构，允许框架返回 INCOMPLETE 和精确缺口；据此补正文锚点/证据后，再以同一结构 `freeze=true` 冻结。经营驱动桥、decisive findings 和 judgment review 没有 freeze 参数，但仍须先读各自精确契约。禁止第一次就用空对象或残缺对象冻结；也禁止因一次冻结失败而跳过后续产物。
8. **固化参数账本**: 调用 write_decision_ledger，覆盖 market price、三种GG、II、V_final、λ、r*、衰减、双安全边际、仓位和买入/减仓/退出触发器。同一指标有多情景时用`canonical=true`显式指定唯一最终口径；其他值必须明确scenario/date/basis或deprecated。正文解释若出现关键值仍须用`[decision: entry_id]`绑定。Ch0、Ch9、Ch12、Ch13、Ch14的最终数字与动作由assemble前的决策编译器生成受保护区块；不得自行生成、删除或改写`TURTLE:DECISION_BLOCK`，禁止复制第二套自由参数
9. **固化估值与决策可靠性账本**: 严格按read_valuation_route结果调用 write_valuation_model_ledger，正文用 `[valuation: model_id]` 绑定模型。company_profile必须写入archetype_id、valuation_route_id和registry_version；每个模型必须引用route_model_id，角色、价值范围、现金流范围不得漂移；route禁用模型必须以status=rejected和理由入账。FCFF 必须配 enterprise value+WACC+EV→股权桥，FCFE/DDM 必须配 equity value+cost of equity。明确名义/实际、税前/税后、币种和日期；永续模型必须报告 r-g、终值占比及折现率+1pct、g-1pct、组合压力三组敏感性动作。至少两个真正独立的假设组；共享假设不能伪装成多模型交叉验证。另须提交cash_access_bridge、parameter_calibrations、model_comparisons、joint_stress_tests和action_policy；未验证现金不得进入主估值，市场价格不得反向校准内在价值参数，非同口径模型不得声称交叉验证，联合压力必须同时覆盖盈利、派息和现金可达性。多模型不得无依据加权平均，最终 chosen value、仓位和 action 必须与 decision ledger/manifest 一致。
10. **固化公司经营驱动桥**: 在前瞻判断前调用 `read_structured_ledger_contract(ledger=financial_driver)` 再调用 `write_financial_driver_bridge`。必须分别覆盖竞争/需求、单位经济、现金转换、资本配置四层；每个OBSERVED项只能引用VERIFIED observation，并明确如何进入已有估值模型输入和决策条目。UNKNOWN必须保留并采用保守处理。金融产品滚动、受限资金释放、在建工程减值等不能被一个标签吞没：分别给出分类依据、实现/结算窗口和行动含义。价格只能进入入场和条件回报，不得作为经营驱动证据或中心路径选择依据。

11. **固化重大主张证据链**: 调用 write_claim_evidence_ledger。重大主张正文用 `[claim: claim_id]`；`chapters` 第一章是该主张的 canonical home，必须原样包含 ledger 的 claim 文本，其他章可只引用 ID。每条链必须包含原始事实、推理、竞争解释、适用条件、置信度及决策影响，并绑定至少一个 decision entry。新统一运行的每条直接支持必须填写VERIFIED `observation_id`，`source_id`必须是该observation对应的`DOC:`身份；CANDIDATE、搜索摘要和报告内部引用都不得作为直接支持。来源同时记录 authority × claim_distance、发布日期/数据截止日、利益冲突、口径匹配和同源组。Markdown 表格可在紧邻位置用 `[table-source: X]` 一次映射整表。
12. **固化中心路径、前瞻判断、竞争解释、阈值与概率**: 调用 write_thesis_test_ledger。先提交唯一的3年或5年 `central_path`，明确选择哪个情景更可能以及为什么；“若X则Y”的敏感性不能替代“X更可能，因为……”的判断。被中心路径选择的 `probability_set` 必须声明为 `TERMINAL_OPERATING_OUTCOME`，并以同一3/5年尺度定义终局；渠道调整、会计确认、库存和其他过程因素必须写入 `mechanism_chains`，不得与经营终局并列占用概率。每条机制链都要绑定情景、领先阈值和到正常化盈利、owner cash、估值、预期回报的传导；每项前瞻判断再用 `mechanism_chain_ids` 连接它。再冻结3-5项 `forward_judgments`：每项必须有方向/区间、期限与resolution_due、证据、竞争解释、领先信号、证伪条件、概率情景身份、官方结果测量规则，并逐项说明如何传导到正常化盈利、owner cash、估值和预期回报；启用 `financial_driver_bridge` 时每项还要用 `financial_driver_ids` 绑定当时四层 bridge 的具体 driver，不能等结果出来再补连；每项可量化判断另冻结一个同一PIT经营信息下的简单 `baseline`，其指标、单位、期限与到期日必须完全相同，且必须写出由已列 evidence 的数值输入可复算的指定公式（持续、公司水平加行业变化或等权驱动）；它只能在结果期比较机制判断的增量信息，绝不参与中心路径选择或读取价格/事后结果；每项还必须登记 `settlement_contract`（冻结 claim ID、PIT 来源、同指标阈值与后果、观察窗口），adapter 不得代填或把区间取中点；正文用 `[central-path: id]` 绑定中心路径。核心 thesis 还必须给出有证据的最强替代解释、能区分两者的观察及可获得时间，并为每个观察写明其在主/反方下各自 `LOW` / `MEDIUM` / `HIGH` 的事前可能性和经济理由（两者必须不同；不得伪造精确概率或贝叶斯因子）、翻转条件，以及翻转后的估值/仓位/动作；正文分别用 `[thesis-test: id]`、`[threshold: id]`、`[probability: id]` 绑定。阈值必须说明历史波动/同行/模型敏感性/合同或监管依据、观测频率、窗口、滚动或连续期规则、季节性、会计口径和合理精度；没有依据的精确数值不得使用。概率必须标明 frequency/base_rate/analyst_subjective/scenario_weight，情景互斥完备且合计100%，每个probability_set必须给出晚于as_of的resolution_due；`base_rate` 的source_ids必须是base_rate_context中至少5个同机制ELIGIBLE `CASE:` ID，否则只能标为analyst_subjective或scenario_weight；主观概率必须给区间，禁止伪精确。
12.1 **冻结前失败预演**: 在中心路径冻结前，先假定这份公司判断已经失败，列出最可能的失败机制。每个材料性失败机制必须转入最强替代解释、`mechanism_chain`、领先阈值或明确 `UNKNOWN`；不能只是再写一张风险清单，不能产生新的评分，也不能以假想失败替代公司证据。
13. **固化洞见账本**: 先确认write_decisive_question_findings已覆盖全部入选question_id，再以合同包 decisive_question_plan、研究结论和 insight_research_brief 为起点。`decisive_question`必须逐字使用某个入选问题，`question_basis.question_id`必须引用对应ID；禁止绕开计划另造问题。调用 write_insight_ledger，仅保留1-3条能改变估值或动作的公司特异洞见；每条绑定 claim/evidence/decision，写出异常→机制链→最强替代解释→区分观察→估值与动作。必须用估值模型反推市场隐含经营路径，不能用“低PE/PB”代替逆向预期；必须说明潜在价值由谁控制、如何兑现、无催化剂时值多少；最强反方成立时动作如何改变。Ch0/Ch14用 `[insight: id]` 绑定。禁止仅因股价跌破某数无条件止损。
14. **独立洞见上限评审**: 洞见账冻结后切换为反方审稿人，调用 write_judgment_review。必须区分“真正差异化洞见”和“只是合格的常规分析”，指出最脆弱跳跃、最需要的新证据，以及拿掉核心洞见后估值与动作是否改变。只能引用现有 insight/evidence/decision/model ID。裁决仅诊断，不得因自评为INSIGHTFUL而放宽任何发布门。
15. **定向研究路由**: 调用 plan_judgment_research(max_tasks_per_run=3)，对execution_queue严格按顺序先调用begin_judgment_research_task，再执行该项required_tools，最后调用complete_judgment_research_task。执行账本会在工具层核验每项maximum tool calls、来源调用和mutation_scope；越界写章/账本与活动任务未完成时assemble会被拒绝。查不到公开信息是有效结果，必须以PUBLIC_INFO_UNAVAILABLE结束，禁止把“未找到”写成正面证据。只有新证据改变主张时才可重写mutation_scope.chapters；禁止全篇扩写、优化分数或修改无关章节。若涉及canonical决策，必须显式decision diff并重新验证全部账本；完成队列后重新调用write_judgment_review。
16. **组装报告**: 结构化账本冻结后调用 read_judgment_generation_handoff(view=JUDGMENT_SYNTHESIS)，以该受控投影复核最终自然语言是否忠实表达公司机制、反方、FJ和财务传导；它不能替代任何 canonical ledger。随后调用 assemble_report；工具先从冻结账本单向编译关键决策区块，再执行完成契约。若返回free_critical_value、protected_block或decision_diff_approval错误，只修对应身份/证据/解释，不得绕过或手工修改受保护区块。新 unified run 自动生成精简投资备忘录与独立15章技术附录

## 模板合约要求
{template_raw if template_raw else '（模板未加载，按标准龟龟报告结构写作）'}

{depth_contract_block}

## 写作深度原则
**深度来自数据、因果分析和推导覆盖，不来自物理行数。有数据的领域写深，没数据的领域不强行编造。**
- 优先用表格承载对比数据。自然段使用2-5个相关句子，只在话题切换时分段。
- 护城河、财务趋势、风险等核心章节的深度由 available data 决定，不由"必须写 X 个子节"驱动。
- 参见模板各章的 CHAPTER_CONTRACT + ITEM_RULE 了解具体该覆盖哪些方面。

## 章节→数据源映射
写作每章前，用对应的 Zone B 数据定位问题，再用 read_section/search_report 回到年报原文核验关键论点；Zone B 非空不等于信息充分。

| 章节 | 首选数据源 | 备用 |
|------|-----------|------|
| Ch1 公司生意 | read_zone_data(mda) + read_zone_data(segments) | read_section(MDA) |
| Ch2 行业位置 | read_zone_data(segments) + get_peer_comparison + get_global_benchmarks | read_section(SEG) |
| Ch3 护城河 | read_zone_data(mda) + get_peer_comparison | read_section(MDA) |
| Ch4 近期变化 | read_zone_data(mda) (最近年) | read_section(MDA) |
| Ch5 经营表现 | read_zone_data(mda) + read_zone_data(segments) | read_section(MDA) |
| Ch7 风险 | read_zone_data(risks) | read_section(RISK) |
| Ch8 治理 | read_zone_data(governance) | read_section(GOV) |
| Ch9 审计 | read_zone_data(audit) | read_section(AUDIT) |

## Zone B 缺失字段的回退策略（V12.7）

以下关键字段可能因年报附注格式不标准而未被 Zone B LLM 提取成功。
写作 Agent 在调用 read_zone_data 后发现以下字段为 "⚠️ 无提取数据" 或空数组时，
**必须用 read_section 直接读对应年报章节**尝试手动提取：

| 缺失字段 | Zone B 文件 | read_section 目标 | 搜索关键词 |
|---------|------------|-------------------|-----------|
| sbc_summary | audit.json | STMT 附注 | "share-based" "股份支付" "购股权" "share award" |
| capitalized_interest_summary | audit.json | STMT 附注 | "capitalised" "资本化" "借款费用资本化" |
| restricted_cash_summary | risks.json | P2 (受限资产) | "pledged" "抵押" "受限" "restricted" |
| related_party_deposits | governance.json | P4 (关联交易) | "财务公司" "treasury" "资金池" "group finance" |
| employee_benefit_trend | governance.json | STMT 附注 | "staff cost" "员工成本" "僱員福利" "employee benefit" |

若 read_section 也找不到 → 在报告中标注 "⚠️ 年报未披露XXX明细"，不要编造。
若能找到 → 直接引用 PDF 原文 `[source: {{year}}_年报.pdf STMT p.X 附注原文]`，绕过 Zone B。

## Spec 定性判断指引（V12.11）

以下三项是 Spec v0.15 要求但无法程序化计算的定性判断。
Zone B 提取结果写入 audit.json / governance.json。写作 Agent 在相关章节中**必须引用并给出判断**：

### 准则差异核查 (Spec Factor3 Step6)
- 数据来源: `audit.json` → `accounting_standards_notes`
- 写入章节: Ch6 财务表现（利润质量评估小节）或 Ch9 风险
- 判断要点:
  - CAS vs HKFRS: 港股用HKFRS，A股用CAS。若公司A+H两地上市→存在准则差异
  - 收入确认: 是否存在激进的收入确认政策（如提前确认、总额法vs净额法）
  - ECL模型: 预期信用损失模型是否充足（对比同业拨备率）
  - HKFRS16: 经营租赁转入表内→负债率上升。需关注表外租赁承诺
  - VIE/SPV: 是否存在未合并的可变利益实体
  - 若无明显差异→标注"未发现重大准则差异"。不要为了凑字数编造问题

### 现金上游障碍 (Spec Factor2 Step4)
- 数据来源: `governance.json` → `parent_cash_upstream_barrier`
- 写入章节: Ch6 财务表现（资产负债表安全性小节）或 Ch7 股东回报
- 判断要点:
  - upstream_barrier_pct > 30% → 大量现金在子公司/关联方，归母股东可及性存疑
  - upstream_barrier_pct > 50% → 显著上游障碍。分红能力取决于子公司能否/愿意向上分配
  - 若无母公司报表数据→标注"年报未附母公司报表，无法评估现金上游障碍"
  - 结合关联交易（P4）和集团财务公司存款一起判断

### ⛔ 特别股息标注规则（V12.18 强制）

当公司存在特别股息（一次性/非经常性分红）时，必须在**全文所有涉及股息率的章节**（Ch0/Ch7/Ch11/Ch12/Ch13）醒目标注：
- "常规DPS=X.XX，特别DPS=Y.YY（一次性，来自[原因]），合计=Z.ZZ"
- "常规股息率=X.X%（可持续），含特别股息率=Z.Z%（不可持续，因特别股息不具重复性）"
- **禁止**仅展示"股息率≈9.2%"而不说明含特别股息。这会让投资者误以为该收益率可持续。
- 股息率主数字以常规DPS为准，含特别股息的数字仅在括号内标注。

### 分红政策 (Spec EV双轨通过条件)
- 数据来源: `governance.json` → `dividend_policy_stated`
- 写入章节: Ch7 股东回报（分红政策小节）或 Ch13 综合决策
- 判断要点:
  - 有明确政策（如"派息率不低于X%"） → 标注为"分红政策明确"
  - 仅有模糊表述（如"维持稳定分红"但无具体比例） → 标注为"分红意愿存在但无硬承诺"
  - 无任何政策声明 → 标注为"⚠️ 无明确分红政策，分红取决于董事会年度决议"
  - 在 Ch13 决策中引用: EV双轨通过条件之一

## 写作密度规则（强制）
报告目标是 **通过语义深度契约的有效信息，而非追求固定文件大小或行数**。

**跨章引用 > 重复叙述**：
- 同一论点（如"净现金占市值47.1%"）只在首次出现时详细展开。后续章只需 `(见 ChX)` 引用。
- 例如 Ch3 分析了资产陷阱 → Ch11 GG 章写 "Ch3 已分析的资产陷阱（净现金/市值47.1%）意味着..." 即可，不要重新展开三段论。
- 同一论点可以用 ChX 交叉引用避免重复展开，但**新出现的数字、时间窗口、阈值或情景参数仍必须保留 `[source: X]`**。同一真实文件可以在不同章节重复引用，不设次数上限。

**禁止冗余句式**（全删，直接写内容）：
- "接下来我们将分析..."
- "通过以上分析可以看出..."
- "综上所述..."
- "值得注意的是..."
- "需要强调的是..."
- "我们将在下一节讨论..."

**Bullet 密度**：
- 每个 bullet 必须有增量信息。如果两个 bullet 说的是同一件事的不同侧面，合并为一个。
- 纯总结性 bullet（"公司整体表现良好"）→ 替换为具体数字 bullet。

## 写作流程（重要）
**本轮写作前**，必须一次调用 `read_report_contract_pack` 读取全部目标章合同；每章再调用相关数据工具，不要逐章重复读取合同，也不要只依赖记忆：
{qual_chapter_prep}
  - Ch2-3 行业/护城河章：必须调用 get_peer_comparison + **get_global_benchmarks** 获取同行列表+百分位排名+国际对标
  - 护城河分析**必须引用百分位数据**（如'毛利率 P16，显著低于行业中位数 19.19%'），不得只做定性描述
  - 每定性章至少嵌入 **1 张同行/行业对比表**（≥4 家可比公司 × ≥5 项指标）
- Ch8 治理章：若 `compute_bundle.factor3.minority_adjustment` 存在（parent_ratio < 0.90），**必须检查 governance.json 的 minority_shareholder_structure 和 dual_role_shareholders**，评估少数股东治理张力。若 Zone J 已生成 `governance_tension.json`，优先引用其分析结论。
- Ch4 最近变化：至少建立“变化→来源→对利润/现金流影响→持续性判断”的证据链；每个核心变化分别引用最新年 mda/segments/financial_trends，不得只在章末来源表集中列名。
- Ch9 风险与否决：每条主要风险必须包含“当前暴露值→触发阈值→验证窗口→来源”；历史事实和未来阈值要明确分开，风险监控表每一行至少能回溯到年报、Zone B 或 compute_bundle。
- 定量章(Ch10-Ch13): 先调 **compute_data_quality** + **get_market_data** + **compute_aa** + compute_gg/compute_ddm
  - Ch11 GG 章：分**粗算**和**精算**两部分。
  **粗算 R(NP)**（因子2）：
  - 裸 NP 收益率：R(NP)_raw = NP₃y / MC × 100（诊断参考，不作为最终GG）
  - 穿透回报率：R(NP)_penetration = NP₃y × M × (1-Q) / MC × 100（V12.5: Spec Factor2 Step8，与精算GG同单位）
  - 否决门使用穿透回报率（而非裸收益率）
  **精算 GG**（因子3）：
  - 公式：GG = AA₃y × M × (1-Q) / MC × 100
  - AA 是极端保守现金结余（全额扣 Capex，含少数股东调整）
  - ⛔ **禁止只输出一个 GG 数字**。必须展示完整推导链：(1)参数表(NP/OE/AA/M/Q/MC/g_adj/II) (2)方法论检查(OCF/NP背离、折旧/NP) (3)**AA 逐年表**—调 compute_aa 展示各年 FCF+收款比率+真实现金收入+趋势判断，不能只写 AA₃y 一个数 (4)GG 公式完全展开代入 (5)三档情景 (6)M 值溯源 (7)HH 偏离 (8)敏感性 (9)反向压力测试 (10)AP/DPO 检测 (11)少数股东调整 (12)λ 推导 (13)治理折价。深度以推导覆盖和证据完整性衡量，不按行数对标旧报告。
  **HH 偏离检查**：|R(NP)_penetration - GG|。若 >2pp，标注"因子2粗算不适用，以精算 GG 为准"并解释差异来源。
  （V12.5 FIX: HH 现在使用穿透R(NP)而非裸R(NP)，两者同单位——均含M×(1-Q)）
  **EV 双轨**（V12.5新增）：若净现金/市值 > 40%，展示 compute_bundle.factor3.gg_ev——用剔除现金后的EV做分母的真实经营回报率。
  **λ 收入敏感性**（V12.5新增）：展示 λ = median(ΔAA/ΔS) 和临界收入倍数（收入需跌到多少GG才跌破II）。
  调 compute_bundle 检查：
  - `factor3.minority_adjustment` → 引用归母比例和 AA 调整幅度
  - `factor3.data_discount_used` → 标注数据折价
  - `factor3.governance_discount_used` → V12.15: 标注治理折价（如有）
  - `factor3.total_discount_used` → V12.15: 展示总折价（数据+治理）
  - `factor3.gg_discounted` → 展示折价后 GG（如存在）
  - Ch11 结尾必须做**反向压力测试**：列出至少 2 个能让 GG<II 的极端情景及所需条件。如果所有合理情景均不改变方向，结论更可信。
  - Ch11 GG 章展示**三种 GG 视角**（V12.13）：
    - **AA GG**（保守）：AA × M × (1-Q) / MC — 极端保守，全额扣 Capex + W 倒挤法
    - **FCFE GG**（现实）：(OCF-Capex) × 归母比例 × M × (1-Q) / MC — 绕开 W，用于低 OCF/Rev、高少数股东公司
    - **Normalized GG**（正常）：只扣维持性 Capex（D&A × G系数）
    - 三种视角差异大时（>2pp），标注分歧来源（如 00506：AA=3.5% vs FCFE=6.4%，差异来自 W 倒挤法 + 少数股东）
    - **OCF/NP 口径说明（强制）**：GG 章首次出现 OCF/NP 时，必须展示两个口径：
      ① 原始口径 OCF/NP=X.XX（年报数据直接计算，来自 `compute_bundle.ocf_np_analysis.raw_mean`）
      ② 若经扰动调整，调整后 OCF/NP=Y.YY（说明剔除了哪些异常年份）
      ③ `compute_bundle.ocf_np_ratio` 是 3y 均值，可能与 raw_mean 不同——必须标注差异来源
      ④ ⛔ 禁止只展示一个 OCF/NP 数字而不说明口径。若 raw_mean 与报告数字偏差>30%，事实对账器会报警。
    - **NP_3y/AA_3y 时间窗口**：Ch11 首次使用 NP_3y 或 AA_3y 时，必须列出使用的年份窗口（来自 `compute_bundle.ocf_np_analysis.years_used`），不可只写"近三年"。
    - **GG vs 股息率背离（强制）**：当 GG > 2 × 股息率时，在 GG 数字旁加注说明："GG=X% 远高于股息率 Y%。差额来自 AA>NP（折旧回流产生的现金超过利润），股东当前实得 ≈ 股息率。GG 反映全部自由现金分给股东的理论值；若超额现金用于回购或高 ROE 再投资，gap 会转化为回报；若沉淀为低效资产，GG 会下行收敛至股息率。"
  - Ch11 结尾展示**外推可信度 5 维评级**（compute_bundle.factor3.extrapolation_rating）：收入波动率/利润调整偏差/HH偏离/商业模式变化/λ可靠性 → overall(high/medium/low)
  - Ch11 必须附上 **λ 敏感性推导**：λ = median(ΔAA/ΔS) over 近3年，含义是每1元收入变动导致的可支配现金变动。临界收入倍数 = 解 GG=II 时的收入 / 当前收入。格式："若营收下跌 X%，GG 将跌破 II"——不能只写结论不写推导。
  - 报告需引用 compute_data_quality 的完整性得分（对标海螺'36/36字段，0%折价'）
  - GG 计算前必须调 get_market_data 检查股本数据可信度，yfinance 股本不准时用年报数据修正
  - **DDM 估值前提限定（Ch12 强制）**：每次出现 DDM 公允价时，必须附带限定说明："DDM 理论价值反映永续分红折现，不代表目标价，仅作为估值上限参考。实际交易价格受市场情绪、流动性、公司治理等多因素影响。"不可将 DDM 公允价等同于"应该值多少钱"。
  - Ch12 DDM 章展示 **P_base 目标价**（V12.5新增）：P_base = MC×(GG/II)/shares，即GG恰好等于II时的公允价。若存在 EV 双轨，同时展示 P_EV。若存在 FCFE GG，同时展示 P_FCFE 作为参考视角。
  - **数值偏差标注**：报告中引用的 DDM/GG/P_base 等计算值，若与 compute_bundle 精确值偏差超过 ±5%，必须加注说明原因（如 DPS 取整、汇率四舍五入）。例："DDM公允价 6.69 HKD（基于DPS=0.282精确计算；若以DPS=0.276计算为6.26 HKD，偏差来自DPS取整差异）"
  - Ch12 章展示 **PE 估值对比**（V12.14）：当前 PE = compute_bundle.factor4.current_pe。用 get_peer_comparison 读取行业 PE 中位数，做对比表。差距>30%时分析来源：归母vs合并口径混淆？少数股东折价？低增长预期？
  - **框架局限性标注（V12.18 强制）**：若 compute_bundle.factor2.framework_limitations 存在，必须在 Ch0（投资要点概览）和 Ch13（综合决策）中以醒目方式展示局限性警告。格式："⚠️ 框架局限性提示：该公司属于[控股平台/轻资产服务/零分红/强周期]类型，Turtle量化模型的底层假设部分不成立。以下GG/DDM结论仅供参考，最终判断以定性分析为准。" 不可隐藏或淡化此警告。
- **写每章前，先读该章的 ITEM_RULE 列表（模板中 `<!-- ITEM_RULE ... -->` 块），逐个检查 `when` 条件是否成立**
  - 成立 → 写入该条目
  - 不确定 → 调用相关工具验证（如 net_cash_pct_mc 是否>100% → 调 compute_aa）
  - 明确不成立 → 跳过
- **写完一章 → 立即 audit_chapter → 不通过就当场重写 → 再审计 → 直到通过，才能写下一章**
  - 不允许攒到全部写完再批量审计——那会导致"发现了违规但不修"
  - 若审计返回 passed=false 或 verdict=regenerate，必须立即重写该章（不要跳到下一章）
- **同一章每轮最多落盘 2 次（首次写入 + 1 次修复，短章也计数）**。预算耗尽后继续下一章；框架会在 fresh-context repair pass 中再处理阻断项。
  - 审计通过（passed=true）→ **立即进入下一章，不要再"优化"**

## 数据引用约束
- **AP/DPO 分析必须调用 compute_aa，引用 ap_driven_analysis 的结果**——不得自行判断"DPO 高=伪现金流"。如果 ap_pct=0%，说明 AP 增速未超过成本增速，DPO 稳定或改善，不应出现"伪现金流"结论。
- **纯算术指标禁止自行计算，必须从工具结果直接引用**：
  - **股息率 → `compute_bundle.factor4.dividend_identity.yield_pretax_pct`**（税后使用 `yield_after_tax_pct`）——这是已完成 DPS 币种转换后的唯一真源，禁止用 DPS÷股价 自己算
  - **PE → `compute_bundle.factor4.current_pe`**——禁止自行计算
  - **PB、ROE、毛利率 等 → `get_financial_trends` 或 `compute_data_quality` 返回的具体值**
  - **M 值 → `compute_gg.ingredients.M.value` + `M.source`**——禁止自己估或写"约XX"
  - 所有算术指标引用时附 `[source: compute_bundle / compute_gg 返回值]`，格式：`股息率 X.X% [source: compute_bundle factor4.dividend_identity.yield_pretax_pct=X.X%]`
- **GG 计算必须调用 compute_gg，引用 ingredients 中的参数。如果 M 值来自 computed_from_DPS/EPS，说明 M 是基于实际分红数据计算的，不应标注为"fallback"。
- GG 计算必须调用 compute_gg，引用 ingredients 中的参数。如果 M 值来自 computed_from_DPS/EPS，说明 M 是基于实际分红数据计算的，不应标注为"fallback"。

## 写作约束
- **所有原始数据断言必须附带可解析的 `[source: 实际文件名或工具名]` 证据锚点**。公式输出同时引用输入真源，并可加 `[derivation: 公式/步骤]`；禁止把“以上推导”“各方法章节”“公告监控”“行业特征”或 `ChX` 填进 source 冒充外部证据。
- 缺失数据标注 "⚠️ 数据不可用"，禁止编造数字
- 金额单位: 百万元 RMB
- 数值保留 1 位小数
- **货币单位规范（强制）**：港股以港币(HKD)为主要计价货币，A股以人民币(RMB)。讨论股价、P_base、DDM公允价、买入价时，必须优先使用交易货币。如需同时展示两种货币，格式为"X.XX HKD (≈ Y.YY RMB)"，不可只写RMB。
- **跨市场/多类别股票（V12.18新增）**：当分析标的与实际持仓是同一公司的不同股票类别时（如A股分析→B股持仓、H股分析→ADR持仓），必须在 Ch0 醒目标注两类股票的价格、汇率、折溢价。GG/AA/护城河等基本面指标不变（同一公司），但 DDM 公允价、P_base、阶梯买入价、安全边际、股息率等价格相关指标必须按实际持仓的股价和币种重算。核心结论（Buy/Hold/Avoid）可能因折溢价而不同——例如 A 股分析说 Hold，B 股折价 30% 后可能变成 Buy。

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

    def _tool_schemas_for_stage(self) -> list[dict[str, Any]]:
        """Expose only tools authorized for the current execution stage."""
        if self._config.pit_mode:
            allowed = {
                "pit_list_sources",
                "pit_read_source",
                "pit_read_framework",
                "pit_write_report",
            }
            return [
                deepcopy(item) for item in self._tools.get_schemas()
                if str(item.get("function", {}).get("name") or "") in allowed
            ]
        if self._config.pit_production_mode:
            allowed = self._pit_production_allowed_tools(self._config.analysis_purpose)
            return [
                deepcopy(item) for item in self._tools.get_schemas()
                if str(item.get("function", {}).get("name") or "") in allowed
            ]
        tool_schemas = (
            self._judgment_tool_schemas()
            if self._config.judgment_task_id
            else self._judgment_synthesis_tool_schemas()
            if self._config.judgment_synthesis
            else self._tools.get_schemas()
        )
        if self._config.binding_only:
            allowed = {
                "list_documents", "read_report_contract_pack",
                "read_structured_ledger_contract", "read_chapter",
                "audit_chapter", "write_chapter",
            }
            tool_schemas = [
                deepcopy(item) for item in tool_schemas
                if str(item.get("function", {}).get("name") or "") in allowed
            ]
            for item in tool_schemas:
                if str(item.get("function", {}).get("name") or "") == "read_structured_ledger_contract":
                    ledger_schema = (
                        item.get("function", {}).get("parameters", {})
                        .get("properties", {}).get("ledger")
                    )
                    if isinstance(ledger_schema, dict):
                        ledger_schema["enum"] = ["decision_binding"]
        elif self._config.synthesis_only:
            frontier, _ = self._structured_repair_frontier()
            if frontier:
                synthesis_forbidden = {
                    # Recomputing the canonical bundle invalidates every CALC
                    # identity already bound into claim/decision ledgers.  It
                    # belongs to preparation, never ledger-only synthesis.
                    "compute_bundle_db",
                    "run_pre_analysis",
                }
                structured_mutations = {
                    "write_decision_manifest", "write_decision_ledger",
                    "write_claim_evidence_ledger", "write_valuation_model_ledger",
                    "write_financial_driver_bridge",
                    "write_thesis_test_ledger", "write_decisive_question_findings",
                    "write_insight_ledger", "write_judgment_review",
                    "plan_judgment_research", "begin_judgment_research_task",
                    "complete_judgment_research_task", "assemble_report",
                }
                tool_schemas = [
                    deepcopy(item) for item in tool_schemas
                    if (
                        str(item.get("function", {}).get("name") or "")
                        not in structured_mutations
                        or str(item.get("function", {}).get("name") or "") == frontier
                    )
                    and str(item.get("function", {}).get("name") or "")
                    not in synthesis_forbidden
                ]
                if frontier == "write_valuation_model_ledger":
                    # Valuation-only repair used to send all ~60 schemas even
                    # though off-frontier calls were rejected later.  Restrict
                    # the model-facing surface to evidence, route, bounded
                    # calculations and the single authorized writer.
                    valuation_frontier_tools = {
                        "write_valuation_model_ledger",
                        "read_structured_ledger_contract", "read_valuation_route",
                        "read_evidence_context", "list_documents", "read_section",
                        "search_report", "get_financial_trends", "read_zone_data",
                        "compute_aa", "compute_gg",
                    }
                    tool_schemas = [
                        item for item in tool_schemas
                        if str(item.get("function", {}).get("name") or "")
                        in valuation_frontier_tools
                    ]
                    best_rejected_path = Path(
                        self._config.output_dir, "valuation_model_best_rejected.json"
                    )
                    try:
                        best_rejected = json.loads(
                            best_rejected_path.read_text(encoding="utf-8")
                        )
                    except (OSError, json.JSONDecodeError):
                        best_rejected = {}
                    rejected_reliability = best_rejected.get("reliability_validation") or {}
                    local_findings = [
                        *list(rejected_reliability.get("invalid_findings") or []),
                        *list(rejected_reliability.get("incomplete_findings") or []),
                    ]
                    if local_findings:
                        local_repair_tools = {
                            "write_valuation_model_ledger",
                            "read_structured_ledger_contract", "read_valuation_route",
                            "read_evidence_context",
                        }
                        tool_schemas = [
                            item for item in tool_schemas
                            if str(item.get("function", {}).get("name") or "")
                            in local_repair_tools
                        ]
        if self._config.repair_targets:
            # Data preparation owns the canonical compute bundle. Any repair
            # pass must treat it as immutable or a one-chapter rewrite can
            # invalidate every CALC identity in the structured ledgers.
            repair_forbidden = {"compute_bundle_db", "run_pre_analysis"}
            tool_schemas = [
                item for item in tool_schemas
                if str(item.get("function", {}).get("name") or "")
                not in repair_forbidden
            ]
        return tool_schemas

    def _structured_repair_frontier(self) -> tuple[str, dict[str, Any]]:
        """Return the first unmet structured ledger and its exact validation."""
        manifest_path = Path(self._config.output_dir, "decision_manifest.json")
        if not manifest_path.is_file():
            return "write_decision_manifest", {
                "state": "MISSING",
                "incomplete_findings": ["decision_manifest.json:missing"],
            }
        sequence = (
            ("decision_ledger_validation.json", "write_decision_ledger"),
            ("claim_evidence_validation.json", "write_claim_evidence_ledger"),
            ("valuation_model_validation.json", "write_valuation_model_ledger"),
            ("decision_reliability_validation.json", "write_valuation_model_ledger"),
            ("financial_driver_bridge_validation.json", "write_financial_driver_bridge"),
            ("thesis_test_validation.json", "write_thesis_test_ledger"),
            ("decisive_question_findings_validation.json", "write_decisive_question_findings"),
            ("insight_validation.json", "write_insight_ledger"),
        )
        try:
            from scripts.report_completion import has_valid_internal_valuation_hypothesis
        except ModuleNotFoundError:
            from report_completion import has_valid_internal_valuation_hypothesis
        internal_valuation_ready = has_valid_internal_valuation_hypothesis(
            self._config.output_dir
        )
        for filename, tool_name in sequence:
            try:
                validation = json.loads(
                    Path(self._config.output_dir, filename).read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                validation = {"state": "MISSING", "incomplete_findings": [filename + ":missing"]}
            if (
                filename == "claim_evidence_validation.json"
                and str(validation.get("state") or "").upper() != "DECISION_READY"
                and not Path(self._config.output_dir, "claim_evidence.json").is_file()
            ):
                try:
                    rejected_validation = json.loads(
                        Path(
                            self._config.output_dir,
                            "claim_evidence_last_rejected_validation.json",
                        ).read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError):
                    rejected_validation = {}
                if rejected_validation:
                    validation = dict(rejected_validation)
                    validation["resume_instruction"] = (
                        "调用write_claim_evidence_ledger(resume_last_rejected=true)，"
                        "只用drop_evidence_ids和claim_chapter_additions做精确修复；"
                        "禁止重新生成完整claims。"
                    )
            state = str(validation.get("state") or validation.get("status") or "MISSING").upper()
            if (
                internal_valuation_ready
                and filename in {
                    "valuation_model_validation.json",
                    "decision_reliability_validation.json",
                }
            ):
                continue
            if filename == "financial_driver_bridge_validation.json" and state in {"REVIEWABLE", "DECISION_READY", "MONITORING"}:
                continue
            if filename == "decision_ledger_validation.json" and state == "INCOMPLETE":
                # Ch0/Ch14 are derived decision surfaces and intentionally stay
                # frozen until the structured ledgers are ready.  A complete,
                # conflict-free canonical ledger may therefore advance as a
                # reviewable two-phase commit; final chapter binding promotes
                # and freezes it after Ch0/Ch14 exist.
                findings = set(validation.get("incomplete_findings") or [])
                allowed_prefixes = (
                    "decision_reference_missing:Ch0:",
                    "decision_reference_missing:Ch14:",
                )
                non_binding = {
                    item for item in findings
                    if item not in {"enforced_ledger_not_frozen", "decision_ready_not_frozen"}
                    and not str(item).startswith(allowed_prefixes)
                }
                required = set(validation.get("required_metric_ids") or [])
                active = set(validation.get("active_metric_ids") or [])
                if (
                    not validation.get("invalid_findings")
                    and not non_binding
                    and required
                    and required.issubset(active)
                ):
                    continue
            if filename == "claim_evidence_validation.json" and state == "INCOMPLETE":
                findings = set(validation.get("incomplete_findings") or [])
                missing_derived_chapters = {
                    chapter for chapter in (0, 14)
                    if not Path(
                        self._config.output_dir, CHAPTERS_SUBDIR, f"_ch{chapter:02d}.md"
                    ).is_file()
                }
                allowed_prefixes = tuple(
                    f"claim_reference_missing:Ch{chapter}:"
                    for chapter in missing_derived_chapters
                )
                non_binding = {
                    item for item in findings
                    if not allowed_prefixes or not str(item).startswith(allowed_prefixes)
                }
                required = set(validation.get("required_chapters") or [])
                covered = set(validation.get("covered_chapters") or [])
                if (
                    missing_derived_chapters
                    and not validation.get("invalid_findings")
                    and not non_binding
                    and required
                    and required.issubset(covered)
                ):
                    continue
            if state not in {"DECISION_READY", "MONITORING"}:
                return tool_name, validation
        return "", {}

    def _run_loop(self) -> None:
        """主循环：LLM 调用 → 工具执行 → 结果注入 → 继续。"""
        tool_schemas = self._tool_schemas_for_stage()

        while self._iterations < self._config.max_iterations:
            if self._config.judgment_task_id:
                # Recompute after every tool batch so the schema itself reserves
                # the final slots for unattempted required tools. Once exhausted,
                # the model can only submit the completion control call.
                tool_schemas = self._judgment_tool_schemas()
            elif self._config.synthesis_only:
                # A successful write advances the dependency frontier. Rebuild
                # schemas every turn so downstream ledgers are not even offered
                # until their prerequisite validation is current and passing.
                tool_schemas = self._tool_schemas_for_stage()
            self._last_offered_tool_names = {
                str(item.get("function", {}).get("name") or "")
                for item in tool_schemas
                if item.get("function", {}).get("name")
            }
            self._iterations += 1

            print(f"  [{self._iterations}] LLM 调用...", end=" ", flush=True)
            call_start = time.time()
            context_chars = len(json.dumps(self._messages, ensure_ascii=False, default=str))
            system_chars = sum(
                len(str(message.get("content", "")))
                for message in self._messages if message.get("role") == "system"
            )

            try:
                resp = self._llm.chat(
                    self._messages,
                    tools=tool_schemas,
                    temperature=self._config.temperature,
                    max_tokens=self._config.max_tokens_per_call,
                )
            except RuntimeError as exc:
                print(f"\n❌ LLM 调用失败: {exc}")
                self._loop_error = str(exc)
                break

            elapsed = time.time() - call_start
            input_tokens = int(resp.usage.get("input", 0) or 0)
            output_tokens = int(resp.usage.get("output", 0) or 0)
            cache_hit = int(resp.usage.get("cache_hit_input", 0) or 0)
            cache_miss = int(resp.usage.get("cache_miss_input", 0) or 0)
            self._usage["calls"] += 1
            self._usage["input_tokens"] += input_tokens
            self._usage["output_tokens"] += output_tokens
            self._usage["cache_hit_input_tokens"] += cache_hit
            self._usage["cache_miss_input_tokens"] += cache_miss
            self._call_usage.append({
                "iteration": self._iterations,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_hit_input_tokens": cache_hit,
                "cache_miss_input_tokens": cache_miss,
                "context_chars": context_chars,
                "system_chars": system_chars,
                "duration_sec": round(elapsed, 3),
                "finish_reason": resp.finish_reason,
                "tool_calls": [call.name for call in resp.tool_calls],
            })
            print(
                f"{elapsed:.1f}s "
                f"(in:{resp.usage.get('input',0)} out:{resp.usage.get('output',0)})"
            )

            # 工具调用
            if resp.has_tool_calls:
                self._handle_tool_calls(resp)
                if (self._config.pit_mode or self._config.pit_production_mode) and self._pit_report_path:
                    break
                if self._config.judgment_task_id and self._judgment_task_finished():
                    break
                if self._config.judgment_synthesis and self._judgment_synthesis_finished():
                    break
                if self._judgment_handoff_requested:
                    print("  ↪ 定向研究队列已生成；当前全文上下文立即交棒。")
                    break
                if self._assembled_this_pass:
                    break
                if self._structured_frontier_completed:
                    print("  ⏹ 当前结构化frontier已通过，立即停止并交还外层验收。")
                    break
                if self._config.binding_only and self._config.repair_targets:
                    missing_targets = set(self._config.repair_targets) - self._passed_chapters
                    if not missing_targets:
                        print("  ⏹ canonical绑定目标全部通过，立即交给下一 fresh-context 批次。")
                        break
                    if all(
                        self._chapter_write_counts.get(idx, 0)
                        >= self._config.max_chapter_attempts_per_pass
                        for idx in missing_targets
                    ):
                        print("  ⏹ canonical绑定目标已耗尽本轮写入预算，立即结束本轮。")
                        break
                if (
                    self._config.source_deepening
                    and self._config.repair_targets
                    and not self._config.synthesis_only
                ):
                    missing_targets = set(self._config.repair_targets) - self._passed_chapters
                    if not missing_targets and not {0, 14}.intersection(self._config.repair_targets):
                        print("  ⏹ 普通章节批次全部通过，立即交给下一 fresh-context 批次。")
                        break
                    if missing_targets and all(
                        self._chapter_write_counts.get(idx, 0)
                        >= self._config.max_chapter_attempts_per_pass
                        for idx in missing_targets
                    ):
                        print(
                            "  ⏹ 来源深化目标均已耗尽本轮写入预算，立即结束本轮；"
                            "禁止继续普通审计/组装空转。"
                        )
                        break
                if (
                    self._config.repair_targets
                    and not self._config.synthesis_only
                    and not self._config.binding_only
                ):
                    missing_targets = set(self._config.repair_targets) - self._passed_chapters
                    if not missing_targets and not {0, 14}.intersection(self._config.repair_targets):
                        print("  ⏹ 普通修复目标全部通过，立即交给下一 fresh-context 批次。")
                        break
                    if missing_targets and all(
                        self._chapter_write_counts.get(idx, 0)
                        >= self._config.max_chapter_attempts_per_pass
                        for idx in missing_targets
                    ):
                        print("  ⏹ 普通修复目标已耗尽本轮写入预算，立即结束本轮。")
                        break
                continue

            # 纯文本（可能已完成，或需要继续）
            if resp.is_text_only:
                self._messages.append(
                    {"role": "assistant", "content": resp.content}
                )
                if self._config.pit_mode or self._config.pit_production_mode:
                    self._loop_error = "pit_writer_finished_without_pit_write_report"
                    break
                if self._config.judgment_task_id:
                    if self._judgment_task_finished():
                        break
                    self._messages.append({
                        "role": "user",
                        "content": (
                            f"任务 {self._config.judgment_task_id} 尚未完成。"
                            "请只执行剩余必要工具，并调用 complete_judgment_research_task；"
                            "不要总结整家公司，也不要组装报告。"
                        ),
                    })
                    continue
                if self._config.judgment_synthesis:
                    if self._judgment_synthesis_finished():
                        break
                    self._messages.append({
                        "role": "user",
                        "content": (
                            "独立综合尚未完成。请先提交完整write_judgment_review，再调用"
                            "finalize_judgment_research_synthesis；禁止搜索或修改报告。"
                        ),
                    })
                    continue
                if self._config.binding_only:
                    missing_targets = sorted(
                        set(self._config.repair_targets) - self._passed_chapters
                    )
                    if not missing_targets:
                        break
                    self._messages.append({
                        "role": "user",
                        "content": (
                            "canonical绑定修复尚未完成，只处理 "
                            + ", ".join(f"Ch{idx}" for idx in missing_targets)
                            + "；读取decision_binding合同及章节后最小write_chapter，"
                            "禁止读取其他ledger或执行研究/综合。"
                        ),
                    })
                    continue
                # 检查是否应该结束
                if self._check_completion():
                    break
                # 追加继续提示
                self._messages.append({
                    "role": "user",
                    "content": (
                        "请继续完成剩余章节。如果所有章节已完成，"
                        + (
                            "请先调用 write_decision_manifest 固化唯一决策身份，再调用 write_decision_ledger 固化canonical参数，"
                            "随后调用 write_claim_evidence_ledger 固化重大主张证据链，再调用 write_valuation_model_ledger 验证估值模型，"
                            "再调用 write_financial_driver_bridge 固化公司经营驱动到估值和动作的传导，并调用 write_thesis_test_ledger 固化竞争解释、阈值和概率，再调用 write_decisive_question_findings 闭环全部入选问题，再调用 write_insight_ledger 固化洞见与精简备忘录，再调用 write_judgment_review 与 plan_judgment_research，最后调用 assemble_report。"
                            if (not self._config.repair_targets or {0, 14}.intersection(self._config.repair_targets))
                            and not self._decision_already_frozen
                            else "本轮不得改写决策 manifest/ledger；请依次验证 write_claim_evidence_ledger、write_valuation_model_ledger、write_financial_driver_bridge、write_thesis_test_ledger、write_decisive_question_findings 与 write_insight_ledger，再调用 write_judgment_review 和 plan_judgment_research 后调用 assemble_report。"
                        )
                    ),
                })
                continue

        if self._iterations >= self._config.max_iterations:
            print(f"  ⚠️ 达到最大迭代次数 ({self._config.max_iterations})，主循环终止，后续由完成契约决定是否可发布")

    def _record_source_research(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """Record only non-empty primary-source/web reads for source-deepening gates."""
        if tool_name not in {"read_section", "search_report", "web_search", "web_fetch"}:
            return
        value = result.get("value")
        if not isinstance(value, dict):
            return
        valid = False
        if tool_name == "read_section":
            valid = bool(str(value.get("text") or "").strip())
        elif tool_name == "search_report":
            valid = int(value.get("total_hits") or 0) > 0 and bool(value.get("hits"))
        elif tool_name == "web_search":
            valid = bool(value.get("results"))
        elif tool_name == "web_fetch":
            fetched_text = str(value.get("text") or "").strip()
            hostile_page = re.search(
                r"_waf_|captcha|访问验证|安全验证|请输入验证码|enable javascript",
                fetched_text,
                re.IGNORECASE,
            )
            valid = int(value.get("char_count") or 0) > 0 and bool(fetched_text) and not hostile_page
        # Preserve failed primary-section attempts.  A small number of frozen
        # chapter plans permit a targeted official-report search fallback when
        # PDF/Markdown section boundaries are unavailable.  The failed attempt
        # is part of the audit proof and is never counted as an effective read.
        if not valid and tool_name != "read_section":
            return
        raw_chapters = args.get("research_for_chapters")
        chapter_ids: list[int] = []
        if isinstance(raw_chapters, (list, tuple, set)):
            for raw in raw_chapters:
                try:
                    chapter_id = int(raw)
                except (TypeError, ValueError):
                    continue
                if 0 <= chapter_id <= 14 and chapter_id not in chapter_ids:
                    chapter_ids.append(chapter_id)
        attribution = "explicit" if chapter_ids else "unassigned"
        # Backward-compatible but conservative inference for primary-section
        # reads only. A section may serve every chapter whose frozen research
        # plan explicitly asks for it. Search/web calls are never guessed.
        if not chapter_ids and tool_name == "read_section":
            try:
                from scripts.research_plan import CHAPTER_RESEARCH_SPECS
            except ModuleNotFoundError:
                from research_plan import CHAPTER_RESEARCH_SPECS
            section = str(args.get("section") or "").upper()
            chapter_ids = sorted(
                idx for idx, spec in CHAPTER_RESEARCH_SPECS.items()
                if section and section in {
                    str(item).upper() for item in spec.get("sections", [])
                }
            )
            attribution = "section_inferred" if chapter_ids else "unassigned"
        self._source_research_calls.append({
            "tool": tool_name,
            "year": args.get("year"),
            "section": args.get("section"),
            "query": str(args.get("query") or "")[:160],
            "url": str(value.get("final_url") or args.get("url") or "")[:300],
            "source": value.get("source"),
            "source_domain": value.get("source_domain"),
            "source_authority": value.get("source_authority"),
            "gate_eligible": bool(valid) and not (
                tool_name == "web_fetch" and value.get("source_authority") == "LOW"
            ),
            "document_id": value.get("document_id"),
            "document_authority": value.get("document_authority"),
            "verification_eligible": value.get("verification_eligible"),
            "error": str(value.get("error") or "")[:300],
            "result_count": len(value.get("results", [])) if tool_name == "web_search" else None,
            "total_hits": value.get("total_hits") if tool_name == "search_report" else None,
            "char_count": value.get("char_count") if tool_name in {"read_section", "web_fetch"} else None,
            "research_for_chapters": chapter_ids,
            "attribution": attribution,
        })

    def _source_calls_for_chapter(self, chapter_index: int) -> list[dict[str, Any]]:
        """Return only source actions explicitly or safely attributed to a chapter."""
        target = int(chapter_index)
        return [
            item for item in self._source_research_calls
            if target in {
                int(raw) for raw in (item.get("research_for_chapters") or [])
                if isinstance(raw, int) or str(raw).isdigit()
            }
        ]

    def _persist_research_execution(self, chapter_index: int) -> None:
        """Persist the real source actions available when a chapter was written.

        This ledger is intentionally separate from report prose.  Mentioning
        "NOTES" in a chapter cannot impersonate an actual read_section call.
        A source action is visible only to chapters it was explicitly tagged
        for (or, for read_section only, safely inferred from the frozen section
        plan). This prevents an industry search for Ch2 from impersonating
        governance research for Ch8.
        """
        try:
            from scripts.research_plan import CHAPTER_RESEARCH_SPECS
        except ModuleNotFoundError:
            from research_plan import CHAPTER_RESEARCH_SPECS
        spec = CHAPTER_RESEARCH_SPECS.get(int(chapter_index), {})
        required = [str(item).upper() for item in spec.get("sections", [])]
        chapter_calls = self._source_calls_for_chapter(chapter_index)
        read_sections = sorted({
            str(item.get("section") or "").upper()
            for item in chapter_calls
            if item.get("tool") == "read_section" and item.get("section")
            and item.get("gate_eligible", True)
        })
        fallback_sections = self._source_section_search_fallbacks(chapter_index, chapter_calls)
        covered = [name for name in required if name in read_sections or name in fallback_sections]
        fiscal_years = sorted({
            int(item["year"])
            for item in chapter_calls
            if item.get("tool") == "read_section" and item.get("year") not in (None, "")
        })
        payload = {
            "version": 3,
            "run_id": self._config.run_id or None,
            "chapters": {},
        }
        path = os.path.join(self._config.output_dir, "research_execution.json")
        try:
            with open(path, encoding="utf-8") as handle:
                existing = json.load(handle)
            same_run = (
                existing.get("run_id") == self._config.run_id
                if self._config.run_id else True
            ) if isinstance(existing, dict) else False
            if isinstance(existing, dict) and same_run:
                payload = existing
        except (OSError, json.JSONDecodeError):
            pass
        payload["version"] = 3
        payload["run_id"] = self._config.run_id or payload.get("run_id")
        global_sections = set(payload.get("global_actual_read_sections", []))
        global_sections.update(read_sections)
        payload["global_actual_read_sections"] = sorted(global_sections)
        chapters = payload.setdefault("chapters", {})
        chapters[str(int(chapter_index))] = {
            "chapter_index": int(chapter_index),
            "pass": self._config.pass_name,
            "enforced": bool(self._config.source_deepening),
            "required_sections": required,
            "actual_read_sections": read_sections,
            "covered_sections": covered,
            "missing_sections": [name for name in required if name not in covered],
            "search_fallback_sections": sorted(fallback_sections),
            "fiscal_years": fiscal_years,
            "tool_counts": {
                name: sum(
                    item.get("tool") == name and item.get("gate_eligible", True)
                    for item in chapter_calls
                )
                for name in ("read_section", "search_report", "web_search", "web_fetch")
            },
            "rejected_web_fetches": [
                {"url": item.get("url"), "authority": item.get("source_authority")}
                for item in chapter_calls
                if item.get("tool") == "web_fetch" and not item.get("gate_eligible", True)
            ],
            "search_queries": [
                item.get("query") for item in chapter_calls
                if item.get("tool") in {"search_report", "web_search"} and item.get("query")
            ],
            "fetched_urls": [
                item.get("url") for item in chapter_calls
                if item.get("tool") == "web_fetch" and item.get("url")
            ],
            "attribution_modes": sorted({
                str(item.get("attribution") or "unassigned") for item in chapter_calls
            }),
            "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def _initialize_research_execution(self) -> None:
        """Start or extend the source ledger for this pipeline run."""
        path = os.path.join(self._config.output_dir, "research_execution.json")
        expected = list(self._config.repair_targets or tuple(range(15)))
        payload: dict[str, Any] = {}
        try:
            with open(path, encoding="utf-8") as handle:
                existing = json.load(handle)
            if (
                isinstance(existing, dict)
                and self._config.run_id
                and existing.get("run_id") == self._config.run_id
            ):
                payload = existing
        except (OSError, json.JSONDecodeError):
            pass
        if not payload:
            payload = {
                "version": 3,
                "run_id": self._config.run_id or None,
                "enforced": bool(self._config.source_deepening),
                "expected_chapters": [],
                "global_actual_read_sections": [],
                "chapters": {},
            }
        payload["version"] = 3
        payload["run_id"] = self._config.run_id or payload.get("run_id")
        payload["enforced"] = bool(payload.get("enforced") or self._config.source_deepening)
        payload["expected_chapters"] = sorted({
            int(idx) for idx in list(payload.get("expected_chapters") or []) + expected
        })
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def _source_research_missing(self, chapter_index: int | None = None) -> list[str]:
        """Return unmet source actions for one chapter or the current pass.

        Requirements come from the chapter research plan. This avoids forcing
        irrelevant web searches into valuation chapters while ensuring that
        industry/governance chapters actually read external source bodies.
        """
        try:
            from scripts.research_plan import CHAPTER_RESEARCH_SPECS
        except ModuleNotFoundError:
            from research_plan import CHAPTER_RESEARCH_SPECS
        indexes = (
            [int(chapter_index)]
            if chapter_index is not None else
            list(self._config.repair_targets or tuple(range(15)))
        )
        if chapter_index is None:
            missing_all: list[str] = []
            for idx in indexes:
                missing_all.extend(
                    f"Ch{idx}: {item}" for item in self._source_research_missing(idx)
                )
            return missing_all
        chapter_calls = self._source_calls_for_chapter(int(chapter_index))
        counts = {
            name: sum(
                item.get("tool") == name and item.get("gate_eligible", True)
                for item in chapter_calls
            )
            for name in ("read_section", "search_report", "web_search", "web_fetch")
        }
        years = {
            int(item["year"])
            for item in chapter_calls
            if item.get("tool") == "read_section"
            and item.get("gate_eligible", True)
            and item.get("year") not in (None, "")
        }
        sections = {
            str(item.get("section") or "").upper()
            for item in chapter_calls
            if item.get("tool") == "read_section" and item.get("gate_eligible", True)
        }
        required_sections = sorted({
            str(section).upper()
            for idx in indexes
            for section in CHAPTER_RESEARCH_SPECS.get(idx, {}).get("sections", [])
        })
        required_tools = {
            str(tool)
            for idx in indexes
            for tool in CHAPTER_RESEARCH_SPECS.get(idx, {}).get("tools", [])
        }
        requirements = {"read_section": max(2, len(required_sections))}
        if "search_report" in required_tools:
            requirements["search_report"] = 3
        if "web_search" in required_tools or "web_fetch" in required_tools:
            requirements["web_search"] = 2
            requirements["web_fetch"] = 1
        missing = [
            f"{name}有效调用 {counts[name]}/{minimum}"
            for name, minimum in requirements.items()
            if counts[name] < minimum
        ]
        if len(years) < 2:
            missing.append(f"年报原文覆盖财年 {len(years)}/2")
        fallback_sections = self._source_section_search_fallbacks(
            int(chapter_index), chapter_calls
        )
        for section in required_sections:
            if section not in sections and section not in fallback_sections:
                missing.append(f"未实际读取 {section} 原文")
        return missing

    def _source_section_search_fallbacks(
        self,
        chapter_index: int,
        chapter_calls: list[dict[str, Any]] | None = None,
    ) -> set[str]:
        """Return sections truthfully covered by official-report search fallback.

        The fallback is deliberately narrow: it must be declared in the frozen
        chapter research spec; an actual section read must have been attempted
        and failed; and eligible searches of official annual-report bodies must
        meet both call and fiscal-year minima.  Search snippets therefore cannot
        silently replace a section read when the section extractor works.
        """
        try:
            from scripts.research_plan import CHAPTER_RESEARCH_SPECS
        except ModuleNotFoundError:
            from research_plan import CHAPTER_RESEARCH_SPECS
        calls = chapter_calls if chapter_calls is not None else self._source_calls_for_chapter(chapter_index)
        rules = CHAPTER_RESEARCH_SPECS.get(int(chapter_index), {}).get(
            "section_search_fallbacks", {}
        )
        covered: set[str] = set()
        for raw_section, raw_rule in rules.items():
            section = str(raw_section).upper()
            rule = raw_rule if isinstance(raw_rule, dict) else {}
            failed_attempt = any(
                item.get("tool") == "read_section"
                and str(item.get("section") or "").upper() == section
                and not item.get("gate_eligible", True)
                for item in calls
            )
            if not failed_attempt:
                continue
            eligible_searches = [
                item for item in calls
                if item.get("tool") == "search_report"
                and item.get("gate_eligible", True)
                and bool(item.get("document_id"))
                and item.get("verification_eligible") is True
                and item.get("year") not in (None, "")
            ]
            years = {int(item["year"]) for item in eligible_searches}
            if (
                len(eligible_searches) >= int(rule.get("minimum_calls", 2))
                and len(years) >= int(rule.get("minimum_years", 2))
            ):
                covered.add(section)
        return covered

    def _handle_tool_calls(self, resp: LlmResponse) -> None:
        """处理 LLM 返回的工具调用。"""
        if self._config.pit_mode or self._config.pit_production_mode:
            self._handle_pit_tool_calls(resp)
            return
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
        persisted_chapters: set[int] = set()
        if not self._last_offered_tool_names:
            fallback_schemas = (
                self._judgment_tool_schemas()
                if self._config.judgment_task_id else
                self._judgment_synthesis_tool_schemas()
                if self._config.judgment_synthesis else
                self._tools.get_schemas()
            )
            self._last_offered_tool_names = {
                str(item.get("function", {}).get("name") or "")
                for item in fallback_schemas
                if item.get("function", {}).get("name")
            }
        for tc in resp.tool_calls:
            args = dict(tc.arguments)
            original_tool_name = tc.name
            safe_aliases = {
                "search_web": "web_search", "fetch_web": "web_fetch",
                "read_report_section": "read_section", "search_annual_report": "search_report",
                "read_financial_statement": "get_financial_statement",
                "read_financial_trends": "get_financial_trends",
                "peer_comparison": "get_peer_comparison",
            }
            if tc.name not in self._last_offered_tool_names:
                alias = safe_aliases.get(str(tc.name).lower())
                if alias and alias in self._last_offered_tool_names:
                    tc.name = alias
                    args["_tool_alias_original"] = original_tool_name
                else:
                    value = {
                        "skipped": True,
                        "error": "tool_not_offered_in_current_stage",
                        "requested_tool": original_tool_name,
                        "offered_tools": sorted(self._last_offered_tool_names),
                        "instruction": "只从offered_tools选择；不要重新研究或重复已成功调用。",
                    }
                    structured_names = {
                        "write_decision_manifest", "write_decision_ledger",
                        "write_claim_evidence_ledger", "write_valuation_model_ledger",
                        "write_financial_driver_bridge",
                        "write_thesis_test_ledger", "write_decisive_question_findings",
                        "write_insight_ledger", "write_judgment_review",
                        "plan_judgment_research", "begin_judgment_research_task",
                        "complete_judgment_research_task", "assemble_report",
                    }
                    if self._config.synthesis_only and original_tool_name in structured_names:
                        self._offstage_structured_calls += 1
                        if self._offstage_structured_calls >= 2:
                            self._structured_no_progress_error = (
                                "结构化综合连续两次调用非当前frontier工具；"
                                "停止本fresh context，禁止继续消耗额度"
                            )
                            value["structured_no_progress"] = True
                            value["error"] = self._structured_no_progress_error
                            self._assembled_this_pass = True
                    result = {"ok": True, "value": value}
                    print(f"    🔧 {original_tool_name}() ⛔ {value['error']}")
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    continue
            args.pop("_tool_alias_original", None)
            if (
                self._config.binding_only
                and tc.name == "read_structured_ledger_contract"
                and args.get("ledger") != "decision_binding"
            ):
                value = {
                    "skipped": True,
                    "error": "binding_only只允许ledger=decision_binding",
                    "requested_ledger": args.get("ledger"),
                }
                result = {"ok": True, "value": value}
                print(f"    🔧 {tc.name}() ⛔ {value['error']}")
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
                continue
            if tc.name == "write_chapter" and args.get("chapter_index") in (None, ""):
                body = str(args.get("content") or "")
                inferred = re.search(r"\bCh(?:apter)?\s*(1[0-4]|[0-9])\b", body, re.IGNORECASE)
                if inferred:
                    args["chapter_index"] = int(inferred.group(1))
            if tc.name == "write_chapter" and self._config.synthesis_only:
                value = {
                    "skipped": True,
                    "synthesis_only": True,
                    "error": "结构化综合专用轮禁止改写任何已通过章节。",
                }
                result = {"ok": True, "value": value}
                print(f"    🔧 {tc.name}() ⛔ {value['error']}")
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
                continue
            structured_prerequisites = {
                "write_valuation_model_ledger": (("claim_evidence_validation.json", {"DECISION_READY", "MONITORING"}),),
                "write_thesis_test_ledger": (
                    ("valuation_model_validation.json", {"DECISION_READY", "MONITORING"}),
                    ("decision_reliability_validation.json", {"DECISION_READY", "MONITORING"}),
                ),
                "write_financial_driver_bridge": (
                    ("valuation_model_validation.json", {"DECISION_READY", "MONITORING"}),
                ),
                "write_decisive_question_findings": (("thesis_test_validation.json", {"DECISION_READY", "MONITORING"}),),
                "write_insight_ledger": (
                    ("thesis_test_validation.json", {"DECISION_READY", "MONITORING"}),
                    ("decisive_question_findings_validation.json", {"DECISION_READY", "MONITORING"}),
                ),
                "write_judgment_review": (("insight_validation.json", {"DECISION_READY", "MONITORING"}),),
            }
            if (
                tc.name in structured_prerequisites
                and not self._config.judgment_task_id
                and (
                    not self._config.repair_targets
                    or bool({0, 14}.intersection(self._config.repair_targets))
                )
            ):
                unmet: list[str] = []
                for filename, accepted_states in structured_prerequisites[tc.name]:
                    try:
                        prerequisite = json.loads(
                            Path(self._config.output_dir, filename).read_text(encoding="utf-8")
                        )
                    except (OSError, json.JSONDecodeError):
                        prerequisite = {}
                    observed = str(prerequisite.get("state") or prerequisite.get("status") or "MISSING").upper()
                    if filename in {
                        "valuation_model_validation.json",
                        "decision_reliability_validation.json",
                    }:
                        try:
                            from scripts.report_completion import has_valid_internal_valuation_hypothesis
                        except ModuleNotFoundError:
                            from report_completion import has_valid_internal_valuation_hypothesis
                        if has_valid_internal_valuation_hypothesis(
                            self._config.output_dir
                        ):
                            observed = "DECISION_READY"
                    if filename == "claim_evidence_validation.json" and observed == "INCOMPLETE":
                        missing_derived = {
                            chapter for chapter in (0, 14)
                            if not Path(
                                self._config.output_dir, CHAPTERS_SUBDIR,
                                f"_ch{chapter:02d}.md",
                            ).is_file()
                        }
                        prefixes = tuple(
                            f"claim_reference_missing:Ch{chapter}:"
                            for chapter in missing_derived
                        )
                        findings = set(prerequisite.get("incomplete_findings") or [])
                        required = set(prerequisite.get("required_chapters") or [])
                        covered = set(prerequisite.get("covered_chapters") or [])
                        if (
                            missing_derived
                            and not prerequisite.get("invalid_findings")
                            and findings
                            and prefixes
                            and all(str(item).startswith(prefixes) for item in findings)
                            and required
                            and required.issubset(covered)
                        ):
                            observed = "DECISION_READY"
                    if observed not in accepted_states:
                        unmet.append(f"{filename}:{observed}")
                if unmet:
                    value = {
                        "skipped": True,
                        "structured_dependency_guard": True,
                        "unmet_prerequisites": unmet,
                        "error": "结构化账本必须按依赖顺序闭环；先修复前置账本再继续。",
                    }
                    result = {"ok": True, "value": value}
                    print(f"    🔧 {tc.name}() ⛔ {value['error']} {'; '.join(unmet)}")
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    continue
            # V12.17: 自动注入 output_dir — 仅框架内部工具
            if "output_dir" not in args and tc.name not in ("web_search", "web_fetch", "WebSearch", "WebFetch"):
                args["output_dir"] = self._config.output_dir
            if self._config.synthesis_only and tc.name in {
                "write_claim_evidence_ledger", "write_valuation_model_ledger",
                "write_thesis_test_ledger", "write_insight_ledger",
            }:
                # Trusted repair contexts may replace a ledger frozen under an
                # older contract, but only the currently exposed dependency
                # frontier can reach this path. The candidate must still pass
                # the complete current validator and leaves an explicit diff.
                args["repair_invalid_frozen"] = True
            if tc.name in {"read_chapter_contract", "read_report_contract_pack"}:
                args["template_path"] = self._config.template_path
            if tc.name == "assemble_report":
                # 运行模式由外层框架决定，禁止模型把验证运行升级为正式发布。
                args["validation_only"] = not self._config.publish_downstream
            if tc.name == "read_report_contract_pack" and self._config.repair_targets:
                args["chapter_indexes"] = list(self._config.repair_targets)
            # 只有真正的服务端内置 WebSearch/WebFetch 才跳过。本仓库也注册了
            # 小写 web_search/web_fetch；DeepSeek 必须实际执行本地工具，过去这里
            # 错把它们当 built-in，导致模型拿到的只是占位符却仍写出 web 来源。
            registered_tools = set(self._tools.list_tools())
            is_server_builtin = tc.name in ("WebSearch", "WebFetch") or (
                tc.name in ("web_search", "web_fetch") and tc.name not in registered_tools
            )
            if (
                tc.name == "assemble_report"
                and not self._config.judgment_task_id
                and "plan_judgment_research" in registered_tools
            ):
                execution_path = Path(self._config.output_dir) / "judgment_research_execution.json"
                try:
                    execution_payload = json.loads(execution_path.read_text(encoding="utf-8"))
                    execution_state = execution_payload.get("state")
                except (OSError, json.JSONDecodeError):
                    execution_payload = {}
                    execution_state = None
                try:
                    research_plan = json.loads(
                        Path(self._config.output_dir, "judgment_research_plan.json").read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError):
                    research_plan = {}
                synthesis_required = bool(
                    (research_plan.get("execution_policy") or {}).get("independent_synthesis_context")
                    or any(
                        isinstance(entry, dict) and bool(entry.get("finding"))
                        for entry in (execution_payload.get("tasks") or {}).values()
                    )
                )
                synthesis_state = self._load_judgment_synthesis().get("state")
                assembly_ready = execution_state == "NO_ACTION" or (
                    execution_state == "COMPLETE"
                    and (not synthesis_required or synthesis_state == "REVIEWED")
                )
                if not assembly_ready:
                    value = {
                        "skipped": True,
                        "judgment_research_guard": True,
                        "error": (
                            "judgment_research_plan_required_before_assembly"
                            if execution_state is None else
                            "independent_judgment_synthesis_required_before_assembly"
                            if execution_state == "COMPLETE" else
                            "queued_judgment_research_must_run_in_fresh_context_before_assembly"
                        ),
                    }
                    result = {"ok": True, "value": value}
                    print(f"    🔧 {tc.name}({_summarize_args(args)}) ⛔ {value['error']}")
                    tool_results.append({
                        "type": "tool_result", "tool_use_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    continue
            try:
                from scripts.judgment_research_execution import (
                    preflight_judgment_tool_call,
                    record_judgment_tool_call,
                )
            except ModuleNotFoundError:
                from judgment_research_execution import (
                    preflight_judgment_tool_call,
                    record_judgment_tool_call,
                )
            judgment_preflight = preflight_judgment_tool_call(
                self._config.output_dir, tc.name, args
            )
            if not judgment_preflight.get("allowed", False):
                value = {
                    "skipped": True,
                    "judgment_research_guard": True,
                    "task_id": judgment_preflight.get("task_id"),
                    "error": judgment_preflight.get("error"),
                }
                result = {"ok": True, "value": value}
                print(f"    🔧 {tc.name}({_summarize_args(args)}) ⛔ {value['error']}")
                tool_results.append({
                    "type": "tool_result", "tool_use_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
                continue
            if is_server_builtin:
                print(f"    🔍 {tc.name}({_summarize_args(args)})", end=" ")
                result = {
                    "ok": True,
                    "value": "[Claude built-in tool — server-side execution]",
                }
                judgment_record = record_judgment_tool_call(
                    self._config.output_dir, tc.name, args, result, verifiable=False
                )
                if judgment_record.get("recorded"):
                    result["judgment_research_meta"] = judgment_record
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": "[Claude built-in tool — server-side execution]",
                })
                print("✅ (built-in)")
                continue
            if (
                tc.name in {
                    "write_decision_manifest", "write_decision_ledger",
                    "write_claim_evidence_ledger", "write_valuation_model_ledger",
                    "write_financial_driver_bridge",
                    "write_thesis_test_ledger", "write_decisive_question_findings",
                    "write_insight_ledger", "write_judgment_review",
                    "plan_judgment_research", "assemble_report",
                }
                and self._config.repair_targets
                and not self._config.synthesis_only
                and not self._config.judgment_task_id
                and not {0, 14}.intersection(self._config.repair_targets)
            ):
                value = {
                    "skipped": True,
                    "structured_synthesis_frozen": True,
                    "decision_frozen": True,
                    "error": "普通章节修复轮禁止修改结构化综合、决策、评审或组装状态。",
                }
                result = {"ok": True, "value": value}
                print(f"    🔧 {tc.name}({_summarize_args(args)}) ⏭ {value['error']}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
                continue
            if tc.name == "assemble_report" and self._config.source_deepening and not self._config.synthesis_only:
                missing_targets = sorted(set(self._config.repair_targets) - self._passed_chapters)
                if missing_targets:
                    value = {
                        "skipped": True,
                        "source_deepening_incomplete": True,
                        "missing_chapters": missing_targets,
                        "error": (
                            "来源驱动深化尚有目标章未写回通过："
                            + ", ".join(f"Ch{idx}" for idx in missing_targets)
                        ),
                    }
                    result = {"ok": True, "value": value}
                    print(f"    🔧 {tc.name}({_summarize_args(args)}) ⏭ {value['error']}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    continue
            # 单章预算守卫：短章也计入。预算耗尽时只冻结该章并继续，
            # 不终止整轮；后续由 fresh-context repair pass 定向处理。
            if tc.name == "write_chapter":
                _ch_idx = int(args.get("chapter_index", -1))
                if _ch_idx in self._passed_chapters:
                    value = {
                        "chapter_index": _ch_idx,
                        "skipped": True,
                        "already_passed_this_pass": True,
                        "passed": True,
                        "error": f"Ch{_ch_idx} 已在本轮通过，冻结正文并立即进入下一章。",
                    }
                    result = {"ok": True, "value": value}
                    print(f"    🔧 {tc.name}({_summarize_args(args)}) ⏭ {value['error']}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    continue
                if (
                    "read_report_contract_pack" in self._tools.list_tools()
                    and _ch_idx not in self._chapter_contract_reads
                ):
                    value = {
                        "chapter_index": _ch_idx,
                        "skipped": True,
                        "contract_required": True,
                        "passed": False,
                        "error": (
                            f"Ch{_ch_idx} 写入前必须先调用 read_report_contract_pack "
                            "加载本轮合同包。"
                        ),
                    }
                    result = {"ok": True, "value": value}
                    print(f"    🔧 {tc.name}({_summarize_args(args)}) ⏭ {value['error']}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    continue
                if self._config.source_deepening:
                    missing_research = self._source_research_missing(_ch_idx)
                    if missing_research:
                        self._pending_source_blocked_writes[_ch_idx] = dict(args)
                        value = {
                            "chapter_index": _ch_idx,
                            "skipped": True,
                            "source_research_required": True,
                            "passed": False,
                            "missing": missing_research,
                            "error": (
                                "来源驱动深化尚未完成，禁止写章。请先实际读取年报和网页正文："
                                + "；".join(missing_research)
                            ),
                        }
                        result = {"ok": True, "value": value}
                        print(f"    🔧 {tc.name}({_summarize_args(args)}) ⏭ {value['error']}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })
                        continue
                body = args.get("content")
                if isinstance(body, str) and "[公司全局记忆" in body:
                    # Memory is author context, never a report heading. Keep the
                    # substantive bullets if the model reused them, strip only
                    # internal wrapper lines before persistence.
                    args["content"] = re.sub(r"^\[公司全局记忆[^\n]*\]\s*\n?", "", body, flags=re.MULTILINE)
                if self._config.repair_targets and _ch_idx not in set(self._config.repair_targets):
                    value = {
                        "chapter_index": _ch_idx,
                        "skipped": True,
                        "target_frozen": True,
                        "passed": False,
                        "error": (
                            f"Ch{_ch_idx} 不在本轮修复目标 "
                            f"{list(self._config.repair_targets)} 中，已由工具层冻结。"
                        ),
                    }
                    result = {"ok": True, "value": value}
                    print(f"    🔧 {tc.name}({_summarize_args(args)}) ⏭ {value['error']}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    continue
                if self._chapter_write_counts.get(_ch_idx, 0) >= self._config.max_chapter_attempts_per_pass:
                    _wc = self._chapter_write_counts[_ch_idx]
                    value = {
                        "chapter_index": _ch_idx,
                        "skipped": True,
                        "attempt_budget_exhausted": True,
                        "attempts": _wc,
                        "passed": False,
                        "error": (
                            f"Ch{_ch_idx} 本轮写入预算已用完（{_wc}/"
                            f"{self._config.max_chapter_attempts_per_pass}）。"
                            "禁止继续重写本章；请立即转到下一章。"
                        ),
                    }
                    result = {"ok": True, "value": value}
                    print(f"    🔧 {tc.name}({_summarize_args(args)}) ⏭ {value['error']}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    chapter_path = Path(self._config.output_dir) / CHAPTERS_SUBDIR / f"_ch{_ch_idx:02d}.md"
                    disk_body = _load_text_file(str(chapter_path))
                    if disk_body:
                        self._chapter_memories[_ch_idx] = _chapter_memory(disk_body, _ch_idx)
                        self._persist_company_memory()
                        self._compact_persisted_chapter_payloads({_ch_idx})
                        self._compact_contract_pack({_ch_idx})
                    continue
            print(f"    🔧 {tc.name}({_summarize_args(args)})", end=" ")
            result = self._tools.execute(tc.name, args)
            ok = result.get("ok", False)
            icon = "✅" if ok else "❌"
            value = result.get("value", result.get("error", ""))
            structured_write_rejected = tc.name in {
                "write_claim_evidence_ledger", "write_valuation_model_ledger",
                "write_financial_driver_bridge",
                "write_thesis_test_ledger", "write_decisive_question_findings",
                "write_insight_ledger", "write_judgment_review",
            } and isinstance(value, dict) and value.get("written") is False and not value.get(
                "decision_revision_proposed"
            )
            task_completion_rejected = (
                tc.name == "complete_judgment_research_task"
                and isinstance(value, dict) and value.get("completed") is False
            )
            if structured_write_rejected or task_completion_rejected:
                validation = value.get("validation") if isinstance(value.get("validation"), dict) else {}
                findings = [
                    *list(validation.get("invalid_findings") or []),
                    *list(validation.get("incomplete_findings") or []),
                    *list(value.get("violations") or []),
                ]
                if value.get("error"):
                    findings.append(str(value["error"]))
                signature = json.dumps(sorted(map(str, findings)), ensure_ascii=False)
                previous_signature, previous_count = self._structured_rejection_state.get(tc.name, ("", 0))
                count = previous_count + 1 if signature and signature == previous_signature else 1
                self._structured_rejection_state[tc.name] = (signature, count)
                total = self._structured_rejection_totals.get(tc.name, 0) + 1
                self._structured_rejection_totals[tc.name] = total
                bounded_frontier_exhausted = bool(
                    self._config.synthesis_only
                    and structured_write_rejected
                    and total >= 2
                )
                if (signature and count >= 2) or bounded_frontier_exhausted:
                    self._structured_no_progress_error = (
                        f"{tc.name} 在当前fresh context已连续两次失败；停止当前真实运行，"
                        "保留精确验证结果，禁止通过穿插读取或下游工具继续消耗额度"
                    )
                    value["structured_no_progress"] = True
                    value["error"] = self._structured_no_progress_error
                    result["value"] = value
                    self._assembled_this_pass = True
            judgment_record = record_judgment_tool_call(
                self._config.output_dir, tc.name, args, result, verifiable=True
            )
            if judgment_record.get("recorded"):
                result["judgment_research_meta"] = judgment_record
            # 来源深化按章节身份提高证据覆盖，不提高字符或分析单元配额。
            if (
                tc.name == "write_chapter"
                and ok
                and self._config.source_deepening
                and isinstance(value, dict)
                and not value.get("skipped", False)
            ):
                try:
                    from scripts.chapter_depth import analyze_chapter_depth, depth_failure_description
                except ModuleNotFoundError:
                    from chapter_depth import analyze_chapter_depth, depth_failure_description
                _premium_content = args.get("content", "")
                _premium_idx = int(args.get("chapter_index", -1))
                _premium_depth = analyze_chapter_depth(
                    _premium_content if isinstance(_premium_content, str) else "",
                    _premium_idx,
                    data_rich=True,
                    quality_profile="source_deepening",
                )
                value["depth"] = _premium_depth
                if _premium_depth.get("status") != "PASS":
                    _premium_error = (
                        "来源深化质量门未通过："
                        + depth_failure_description(_premium_depth)
                        + "。请补真实证据或缺失研究闭环；禁止重复和空泛补字。"
                    )
                    value["passed"] = False
                    value["short_content"] = True
                    value["error"] = _premium_error
                    _premium_audit = value.get("audit")
                    if isinstance(_premium_audit, dict):
                        _premium_audit["passed"] = False
                        _premium_audit["verdict"] = "fail"
                        _premium_audit["error_count"] = int(_premium_audit.get("error_count", 0)) + 1
                        _premium_audit.setdefault("violations", []).append({
                            "rule": "P3_SOURCE_DEEPENING_DEPTH",
                            "severity": "error",
                            "desc": _premium_error,
                        })
                result["value"] = value
            preview = str(value)[:80] if ok else str(value)[:80]
            print(f"{icon} {preview}")

            if ok:
                self._record_source_research(tc.name, args, result)

            if tc.name == "assemble_report" and ok:
                self._assembled_this_pass = True
            if (
                self._config.synthesis_only
                and tc.name == "write_valuation_model_ledger"
                and ok
                and isinstance(value, dict)
                and value.get("decision_revision_proposed") is True
            ):
                # Preserve a reliability-valid valuation hypothesis without
                # retrying it in the same paid context.  It is not a user
                # approval surface; the next workflow stage must complete a
                # full-report synthesis transaction before final review.
                self._structured_frontier_completed = True
                value["frontier_completed"] = True
            if (
                self._config.synthesis_only
                and tc.name == self._initial_structured_frontier
                and ok
                and isinstance(value, dict)
                and value.get("written") is True
                and str((value.get("validation") or {}).get("state") or "").upper()
                in {"DECISION_READY", "MONITORING"}
            ):
                self._structured_frontier_completed = True
                value["frontier_completed"] = True
            if tc.name == "plan_judgment_research" and ok:
                execution_path = Path(self._config.output_dir) / "judgment_research_execution.json"
                try:
                    execution = json.loads(execution_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    execution = {}
                self._judgment_handoff_requested = execution.get("state") == "PENDING"
            if tc.name == "read_chapter_contract" and ok and isinstance(value, dict) and value.get("ok"):
                try:
                    self._chapter_contract_reads.add(int(value.get("chapter_index", -1)))
                except (TypeError, ValueError):
                    pass
            if tc.name == "read_report_contract_pack" and ok and isinstance(value, dict) and value.get("ok"):
                for idx in value.get("chapter_indexes", []):
                    try:
                        self._chapter_contract_reads.add(int(idx))
                    except (TypeError, ValueError):
                        pass

            # 后置计数：所有实际落盘尝试都计数，包括 short_content。
            if tc.name == "write_chapter":
                _ch_idx = int(args.get("chapter_index", -1))
                _val = result.get("value", {})
                if isinstance(_val, dict):
                    _did_write = (
                        result.get("ok", False)
                        and not _val.get("skipped", False)
                    )
                    if _did_write:
                        self._chapter_write_counts[_ch_idx] = self._chapter_write_counts.get(_ch_idx, 0) + 1
                        if not self._config.binding_only:
                            self._persist_research_execution(_ch_idx)
                        attempt = self._chapter_write_counts[_ch_idx]
                        audit = _val.get("audit", {}) if isinstance(_val.get("audit"), dict) else {}
                        depth = _val.get("depth", {}) if isinstance(_val.get("depth"), dict) else {}
                        binding = (
                            _val.get("decision_binding_validation", {})
                            if isinstance(_val.get("decision_binding_validation"), dict)
                            else {}
                        )
                        passed = (
                            bool(audit.get("passed", False))
                            and depth.get("status") == "PASS"
                            and _val.get("passed") is not False
                            and binding.get("state") != "INVALID"
                        )
                        self._chapter_attempt_log.append({
                            "chapter_index": _ch_idx,
                            "attempt": attempt,
                            "pass": self._config.pass_name,
                            "passed": passed,
                            "short_content": bool(_val.get("short_content", False)),
                            "char_count": _val.get("char_count"),
                            "depth_status": depth.get("status"),
                            "depth_failures": depth.get("failures", []),
                            "audit_verdict": audit.get("verdict"),
                            "decision_binding_state": binding.get("state"),
                        })
                        body = args.get("content")
                        # Do not compact or summarize a failed draft: the same
                        # author needs its full body to make the in-pass repair.
                        # Only a semantically/audit-passed chapter is safe to fold.
                        if passed and isinstance(body, str) and body.strip():
                            persisted_chapters.add(_ch_idx)
                            self._passed_chapters.add(_ch_idx)
                            self._chapter_memories[_ch_idx] = _chapter_memory(body, _ch_idx)
                            self._persist_company_memory()
                        elif not passed:
                            self._passed_chapters.discard(_ch_idx)

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

        self._messages.append({
            "role": "user",
            "content": tool_results,
        })
        if persisted_chapters:
            self._compact_persisted_chapter_payloads(persisted_chapters)
            self._compact_contract_pack(persisted_chapters)
        self._compact_duplicate_tool_results()
        # Tool calls in the current batch may have completed the source gate
        # for a draft rejected in an earlier batch.  Replay the retained bytes
        # as a normal write_chapter call so every existing audit/depth/binding
        # guard still runs.  Pop first to make recursion bounded even if a new
        # guard rejects the replay for another reason.
        ready = [
            idx for idx in sorted(self._pending_source_blocked_writes)
            if idx not in self._passed_chapters and not self._source_research_missing(idx)
        ]
        if ready:
            idx = ready[0]
            pending_args = self._pending_source_blocked_writes.pop(idx)
            print(f"    ♻️ Ch{idx} 来源门已补齐，自动重放暂存稿（不再调用模型生成正文）")
            self._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
                id=f"auto-source-ready-ch{idx}-{self._iterations}",
                name="write_chapter",
                arguments=pending_args,
            )]))

    def _handle_pit_tool_calls(self, resp: LlmResponse) -> None:
        """Execute PIT tools without normal-output injection or research hooks."""
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
        allowed = self._pit_production_allowed_tools(self._config.analysis_purpose) if self._config.pit_production_mode else {
            "pit_list_sources",
            "pit_read_source",
            "pit_read_framework",
            "pit_write_report",
        }
        results: list[dict[str, Any]] = []
        for tc in resp.tool_calls:
            if tc.name not in allowed or tc.name not in self._last_offered_tool_names:
                from turtle_agent.tools.pit_read_tools import audit_pit_tool_denial
                audit_pit_tool_denial(tc.name)
                result: dict[str, Any] = {
                    "ok": False,
                    "error": "pit_tool_not_offered",
                    "requested_tool": tc.name,
                }
            else:
                result = self._tools.execute(tc.name, dict(tc.arguments))
            value = result.get("value") if isinstance(result, dict) else None
            if (
                tc.name == "pit_write_report"
                and result.get("ok") is True
                and isinstance(value, dict)
                and value.get("written") is True
            ):
                self._pit_report_path = str(value.get("report_path") or "")
            if (
                tc.name == "pit_assemble_report"
                and result.get("ok") is True
                and isinstance(value, dict)
                and value.get("path")
            ):
                self._pit_report_path = str(value["path"])
            results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })
        self._messages.append({"role": "user", "content": results})

    def _compact_contract_pack(self, chapter_indexes: set[int]) -> None:
        """Remove only completed chapters from the one-shot contract pack."""
        tool_ids: set[str] = set()
        for message in self._messages:
            content = message.get("content")
            if message.get("role") != "assistant" or not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") == "tool_use" and block.get("name") == "read_report_contract_pack":
                    tool_ids.add(str(block.get("id", "")))
        for message in self._messages:
            content = message.get("content")
            if message.get("role") != "user" or not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") != "tool_result" or str(block.get("tool_use_id", "")) not in tool_ids:
                    continue
                raw = block.get("content")
                if not isinstance(raw, str):
                    continue
                try:
                    envelope = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                value = envelope.get("value") if isinstance(envelope, dict) else None
                chapters = value.get("chapters") if isinstance(value, dict) else None
                if not isinstance(chapters, dict):
                    continue
                changed = False
                for idx in chapter_indexes:
                    item = chapters.get(str(idx))
                    if isinstance(item, dict) and isinstance(item.get("content"), str):
                        item["content"] = "[合同已执行；公司结论保留在全局记忆]"
                        changed = True
                if changed:
                    compacted = json.dumps(envelope, ensure_ascii=False, default=str)
                    if len(raw) > len(compacted):
                        self._chapter_contract_chars_compacted += len(raw) - len(compacted)
                    block["content"] = compacted

    def _compact_persisted_chapter_payloads(self, chapter_indexes: set[int]) -> None:
        """Drop redundant chapter bodies from history after they are safely on disk."""
        for message in self._messages:
            content = message.get("content")
            if message.get("role") == "assistant" and isinstance(content, list):
                for block in content:
                    if block.get("type") != "tool_use" or block.get("name") != "write_chapter":
                        continue
                    payload = block.get("input")
                    if not isinstance(payload, dict):
                        continue
                    try:
                        chapter_index = int(payload.get("chapter_index", -1))
                    except (TypeError, ValueError):
                        continue
                    body = payload.get("content")
                    if chapter_index in chapter_indexes and isinstance(body, str) and len(body) > 200:
                        replacement = self._chapter_memories.get(
                            chapter_index,
                            f"[已落盘 Ch{chapter_index}，正文请用 read_chapter 按需读取]",
                        )
                        self._context_chars_compacted += len(body) - len(replacement)
                        payload["content"] = replacement
            if message.get("role") == "user" and isinstance(content, list):
                for block in content:
                    if block.get("type") != "tool_result" or not isinstance(block.get("content"), str):
                        continue
                    raw = block["content"]
                    try:
                        payload = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    value = payload.get("value") if isinstance(payload, dict) else None
                    if not isinstance(value, dict) or "content" not in value:
                        continue
                    try:
                        chapter_index = int(value.get("chapter_index", -1))
                    except (TypeError, ValueError):
                        continue
                    body = value.get("content")
                    if chapter_index in chapter_indexes and isinstance(body, str) and len(body) > 200:
                        value["content"] = self._chapter_memories.get(
                            chapter_index,
                            f"[Ch{chapter_index} 已更新并落盘，旧正文已从上下文压缩]",
                        )
                        compacted = json.dumps(payload, ensure_ascii=False, default=str)
                        self._context_chars_compacted += len(raw) - len(compacted)
                        block["content"] = compacted

        # A chapter contract is a mechanical instruction payload. Once the
        # chapter is safely persisted its global-memory summary remains, while
        # the contract can be re-read if a later repair needs it.
        tool_names: dict[str, tuple[str, int | None]] = {}
        for message in self._messages:
            content = message.get("content")
            if message.get("role") != "assistant" or not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                payload = block.get("input") if isinstance(block.get("input"), dict) else {}
                try:
                    idx = int(payload.get("chapter_index", -1))
                except (TypeError, ValueError):
                    idx = None
                tool_names[str(block.get("id", ""))] = (str(block.get("name", "")), idx)
        for message in self._messages:
            content = message.get("content")
            if message.get("role") != "user" or not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") != "tool_result" or not isinstance(block.get("content"), str):
                    continue
                tool_name, idx = tool_names.get(str(block.get("tool_use_id", "")), ("", None))
                if tool_name != "read_chapter_contract" or idx not in chapter_indexes:
                    continue
                raw = block["content"]
                replacement = json.dumps({
                    "ok": True,
                    "value": {"chapter_index": idx, "contract_applied": True, "content": "[章节合同已执行；需要时可重新读取]"},
                }, ensure_ascii=False)
                if len(raw) > len(replacement):
                    self._chapter_contract_chars_compacted += len(raw) - len(replacement)
                    block["content"] = replacement

    def _compact_duplicate_tool_results(self) -> None:
        """Keep the latest identical data read, never multiple stale copies."""
        call_meta: dict[str, tuple[str, str]] = {}
        excluded = {"write_chapter", "audit_chapter", "assemble_report", "write_decision_manifest", "write_decision_ledger", "write_valuation_model_ledger", "write_claim_evidence_ledger", "write_financial_driver_bridge", "write_thesis_test_ledger", "write_decisive_question_findings", "write_insight_ledger", "write_judgment_review", "plan_judgment_research", "read_chapter_contract", "read_report_contract_pack", "read_chapter"}
        for message in self._messages:
            content = message.get("content")
            if message.get("role") != "assistant" or not isinstance(content, list):
                continue
            for block in content:
                name = str(block.get("name", ""))
                if block.get("type") != "tool_use" or name in excluded:
                    continue
                payload = block.get("input") if isinstance(block.get("input"), dict) else {}
                normalized = {k: v for k, v in payload.items() if k not in {"output_dir", "template_path"}}
                signature = name + ":" + json.dumps(normalized, ensure_ascii=False, sort_keys=True, default=str)
                call_meta[str(block.get("id", ""))] = (name, signature)
        occurrences: dict[str, list[dict[str, Any]]] = {}
        for message in self._messages:
            content = message.get("content")
            if message.get("role") != "user" or not isinstance(content, list):
                continue
            for block in content:
                if block.get("type") != "tool_result" or not isinstance(block.get("content"), str):
                    continue
                meta = call_meta.get(str(block.get("tool_use_id", "")))
                if meta:
                    occurrences.setdefault(meta[1], []).append(block)
        for signature, blocks in occurrences.items():
            for block in blocks[:-1]:
                raw = block["content"]
                replacement = json.dumps({"ok": True, "value": f"[旧的重复工具结果已压缩；以同参数最新返回为准: {signature[:120]}]"}, ensure_ascii=False)
                if len(raw) > len(replacement):
                    self._duplicate_result_chars_compacted += len(raw) - len(replacement)
                    block["content"] = replacement

    def run_metrics(self) -> dict[str, Any]:
        """Return token and chapter-attempt telemetry for run diagnostics."""
        first_attempts: dict[int, dict[str, Any]] = {}
        for item in self._chapter_attempt_log:
            first_attempts.setdefault(int(item["chapter_index"]), item)
        first_passed = sum(bool(item.get("passed")) for item in first_attempts.values())
        return {
            "usage": dict(self._usage),
            "calls": list(self._call_usage),
            "chapter_attempts": list(self._chapter_attempt_log),
            "chapters_written": len(first_attempts),
            "first_attempt_passed": first_passed,
            "first_attempt_hit_rate": (
                first_passed / len(first_attempts) if first_attempts else None
            ),
            "rewrite_attempts": max(0, len(self._chapter_attempt_log) - len(first_attempts)),
            "context_chars_compacted": self._context_chars_compacted,
            "chapter_contract_chars_compacted": self._chapter_contract_chars_compacted,
            "duplicate_result_chars_compacted": self._duplicate_result_chars_compacted,
            "company_memory_chars": sum(len(value) for value in self._chapter_memories.values()),
            "source_research_calls": list(self._source_research_calls),
            "source_research_missing": self._source_research_missing() if self._config.source_deepening else [],
            "system_prompt_chars": next((
                len(str(message.get("content", "")))
                for message in self._messages if message.get("role") == "system"
            ), 0),
        }

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

        # 仅接受明确的工具组装成功信号；文本声明本身不再视为完成。
        recent = self._messages[-2:] if len(self._messages) >= 2 else self._messages
        for msg in reversed(recent):
            blocks = msg.get("content")
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                try:
                    payload = json.loads(block.get("content", "{}"))
                except (TypeError, json.JSONDecodeError):
                    continue
                value = payload.get("value", {})
                if isinstance(value, dict) and value.get("tool_name") == "assemble_report":
                    completion = value.get("completion", {})
                    if completion.get("status") in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
                        return True
        return False

    # ------------------------------------------------------------------
    # 报告组装
    # ------------------------------------------------------------------

    def _assemble_report(self) -> str:
        """委托唯一组装入口，避免绕过完成契约和质量门。"""
        from turtle_agent.tools.write_tools import assemble_report

        result = assemble_report(
            output_dir=self._config.output_dir,
            company_name=self._context.get("company_name", ""),
            ts_code=self._config.code,
            validation_only=not self._config.publish_downstream,
        )
        if result.get("completion", {}).get("status") not in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
            return str(result.get("path", ""))
        return str(result.get("path", ""))

    def _compress_report(self, report_path: str) -> str:
        """全局去重压缩：一次 LLM 调用，去除跨章重复，提升信息密度。

        返回压缩后的报告路径（同路径覆盖）。
        """
        if not os.path.exists(report_path):
            return report_path

        with open(report_path, encoding="utf-8") as f:
            content = f.read()

        # 跳过太短的报告（<3000 字）或已压缩过的
        if len(content) < 3000 or "[📦 已压缩]" in content[:500]:
            return report_path

        print(f"  📦 全局去重压缩 ({len(content):,} chars)...", end=" ", flush=True)
        t0 = time.time()

        compress_prompt = f"""你是一个报告压缩器。以下是一份投资分析报告，请压缩它。

## 压缩规则（重要）
1. **同一论点只出现在首次出现的章节**。后续章只需写 "(见 ChX)" 引用，不要复述。
2. **合并重复段落**。如果 Ch3 护城河和 Ch11 GG 都分析了净现金/资产陷阱，保留 Ch3 的详细版，Ch11 简化为 "Ch3 已分析的资产陷阱（净现金/市值47.1%）意味着..."
3. **删除冗余铺垫**。"接下来我们将分析..."、"通过以上分析可以看出..."、"综上所述..." — 全删。
4. **证据引用保留**。所有 `[source: X]` 标注必须原样保留。
5. **数字和表格保留**。所有数据不压缩。
6. **总长度缩减 20-30%**，主要通过去重实现，不是删内容。

## 压缩后的报告
直接在下面输出完整压缩后的 markdown 报告。不要省略任何章节——是全部 15 章，每章都要有。
不要加任何解释文字，直接输出报告正文。

{content}"""

        try:
            resp = self._llm.chat(
                messages=[{"role": "user", "content": compress_prompt}],
                temperature=0.2,
                max_tokens=32768,
            )

            compressed = resp.content.strip()
            # 清理可能的 markdown fence
            if compressed.startswith("```"):
                lines = compressed.split("\n")
                compressed = "\n".join(lines[1:])
                if compressed.endswith("```"):
                    compressed = compressed[:-3]

            if len(compressed) > len(content) * 0.3:  # 至少保留了 30%
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(compressed + "\n\n[📦 已压缩]")
                elapsed = time.time() - t0
                reduction = (1 - len(compressed) / len(content)) * 100
                print(f"{len(compressed):,} chars (-{reduction:.0f}%, {elapsed:.0f}s)")
            else:
                print(f"⚠️ 压缩后过短 ({len(compressed)} chars)，保留原版")
        except Exception as exc:
            print(f"⚠️ 压缩失败: {exc}")

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


def _validate_tracking_report(report_text: str, report_type: str, fiscal_year: int | None = None) -> tuple[int, list[str]]:
    """V12.20: 软校验 — 检查非 annual 报告是否做到了 tracking。

    Returns:
        (score, issues): score 0-100, issues 是问题描述列表。
    """
    if report_type == 'annual':
        return 100, []
    issues = []
    first_20pct = report_text[:max(len(report_text)//5, 500)].lower()

    # 1. 前 20% 是否包含变化总结关键词？
    change_kws = ['变化', '改善', '恶化', '维持', '不变', '同比', '什么变了', '什么没变']
    if not any(kw in first_20pct for kw in change_kws):
        issues.append('报告前20%缺少变化总结关键词（变化/改善/恶化/维持/不变/同比）')

    # 2. 是否明确提到了归因类型？
    class_kws = ['seasonal', 'cyclical', 'structural', 'one_off', 'accounting', '周期性', '季节性', '结构性', '一次性']
    if not any(kw in first_20pct for kw in class_kws):
        issues.append('未在报告开头明确提到 change_classification（seasonal/cyclical/structural/one_off/accounting）')

    # 3. 是否沿用了过时时态？
    if fiscal_year:
        stale = [f'等待{fiscal_year-1}年年报', f'等待{fiscal_year-2}年年报']
        for sp in stale:
            if sp in report_text:
                issues.append(f'包含过时时态："{sp}"')

    # 4. 是否错误地重算了 GG？（检查是否出现 "GG = " 后面跟百分比且不是继承自年报的表述）
    if 'gg = ' in first_20pct or 'gg=' in first_20pct:
        # 检查上下文是否说明是继承
        if '继承' not in first_20pct and '沿用' not in first_20pct and '年报锚' not in first_20pct:
            issues.append('报告开头重算了 GG（Q1/Q3 应继承年报锚，不应重新推导）')

    score = max(0, 100 - len(issues) * 25)
    return score, issues


def _format_tracking_context(tracking_context: dict[str, Any] | None) -> str:
    if not tracking_context:
        return ''
    output_dir = str(tracking_context.get('output_dir') or '').strip()
    current = tracking_context.get('current') or {}
    if not current:
        return ''
    report_type = _normalize_tracking_report_type(current.get('report_type'))
    previous = tracking_context.get('previous_latest') or {}
    annual = tracking_context.get('latest_annual') or {}

    parts: list[str] = ["## 连续跟踪上下文"]
    parts.append(
        f"- 当前节点: {current.get('report_type_label') or _tracking_label(report_type)}"
        f" | fiscal_year={current.get('fiscal_year') or 'N/A'}"
        f" | period_end={current.get('period_end') or 'N/A'}"
    )
    parts.append(
        f"- 比较口径: {current.get('metric_comparison_basis') or ('unavailable' if report_type == 'annual' else 'yoy')}"
        f" | 预设归因={current.get('change_classification') or '待判断'}"
    )
    if current.get('comparison_summary'):
        parts.append(f"- 现有跟踪摘要: {current.get('comparison_summary')}")

    if previous and any(previous.get(k) for k in ('summary', 'period_end', 'fiscal_year', 'report_type_label')):
        parts.append('- 上一正式节点:')
        parts.append(
            f"  {previous.get('report_type_label') or '未知'}"
            f" | fiscal_year={previous.get('fiscal_year') or 'N/A'}"
            f" | period_end={previous.get('period_end') or 'N/A'}"
            f" | GG={previous.get('gg') if previous.get('gg') is not None else 'N/A'}"
            f" | DDM={previous.get('ddm') if previous.get('ddm') is not None else 'N/A'}"
        )
        if previous.get('summary'):
            parts.append(f"  摘要: {previous.get('summary')}")

    if annual and any(annual.get(k) is not None for k in ('gg', 'ddm', 'p_base', 'upside_pct')):
        parts.append('- 最近年报估值锚:')
        parts.append(
            f"  fiscal_year={annual.get('fiscal_year') or 'N/A'}"
            f" | period_end={annual.get('period_end') or 'N/A'}"
            f" | GG={annual.get('gg') if annual.get('gg') is not None else 'N/A'}"
            f" | DDM={annual.get('ddm') if annual.get('ddm') is not None else 'N/A'}"
            f" | P_base={annual.get('p_base') if annual.get('p_base') is not None else 'N/A'}"
            f" | upside={annual.get('upside_pct') if annual.get('upside_pct') is not None else 'N/A'}"
        )
        if annual.get('summary'):
            parts.append(f"  年报摘要: {annual.get('summary')}")

    # V12.20 comparison context
    qc = tracking_context.get('quarterly_comparison') or {}
    if qc:
        parts.append('')
        parts.append('## 本次 comparison 数据包（从 _comparison.json 读取）')
        parts.append(f"- 营收同比: {qc.get('revenue_yoy') or 'N/A'}")
        parts.append(f"- 毛利率变化: {qc.get('gross_margin_delta') or 'N/A'}")
        parts.append(f"- 归母净利同比: {qc.get('np_yoy') or 'N/A'}")
        parts.append(f"- OCF同比: {qc.get('ocf_yoy') or 'N/A'}")
        if qc.get('key_changes'):
            parts.append(f"- 关键变化: {', '.join(qc['key_changes']) if isinstance(qc['key_changes'], list) else qc['key_changes']}")

    if report_type == 'annual':
        parts.append('- 当前是年报节点：这是新的 canonical baseline，应完整重校准 thesis、GG、DDM、目标仓位。')
    else:
        parts.append('')
        parts.append('## 跟踪报告写作规则（软约束 + comparison-first 思考顺序）')
        parts.append('')
        parts.append('你不是在写一份新的全量年报。你是在回答一个问题：')
        parts.append('**这次的新数据，是否改变了我们对这家公司的判断？**')
        parts.append('')
        parts.append('### 强制思考顺序（报告必须按此结构开头）')
        parts.append('')
        parts.append('在写任何背景介绍之前，你必须先完成以下 **跟踪判断**，并放在报告最前面：')
        parts.append('')
        parts.append('1. **什么变了**：（列出 2-5 条从本次新数据中看到的关键变化，每条一行）')
        parts.append('2. **什么没变**：（列出 2-3 条上次分析中维持不变的判断）')
        parts.append('3. **变化归因**：seasonal / cyclical / structural / one_off / accounting（选一个）')
        parts.append('4. **对 thesis 的影响**：维持 / 强化 / 弱化 / 待确认')
        parts.append('5. **下一次验证点**：（如 2026H1 中报 / 2026 年报）')
        parts.append('')
        parts.append('### 完成跟踪判断后')
        parts.append('- 如果 thesis 影响是「维持」且变化归因是 seasonal/one_off → 报告可以较短，不必重写公司简介和商业模式')
        parts.append('- 如果 thesis 影响是「弱化」或归因是 structural → 展开分析，解释为什么可能需要调整估值锚或仓位')
        parts.append('- annual anchor 的 GG/DDM/P_base 默认沿用，不重新推导')
        parts.append('')
        parts.append('')
        parts.append('')
        parts.append('### save_comparison 工具（V12.20 — 报告写完后必须调用）')
        parts.append('完成报告后、assemble_report 之前，调用 save_comparison 保存结构化对比。')
        parts.append(f'  save_comparison(output_dir="{output_dir}",')
        parts.append('    previous_node=”上一节点描述”,')
        parts.append('    revenue_yoy=”+8.2%”, gross_margin_delta=”+2.3pp”,')
        parts.append('    change_classification=”cyclical”, thesis_impact=”维持”)')
        parts.append('')
        parts.append('### 时态规则')
        current_fy = current.get('fiscal_year')
        if current_fy:
            next_fy = int(current_fy) + 1
            parts.append(f'- 当前财年为 {current_fy}，follow-up 应面向 {current_fy}H1/{current_fy}Q3/{next_fy}年报')
            parts.append(f'- 禁止提及”{int(current_fy)-1}年年报”作为”待等待”的对象')
    return "\n".join(parts)


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
