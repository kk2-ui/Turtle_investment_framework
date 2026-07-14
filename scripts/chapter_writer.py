#!/usr/bin/env python3
"""chapter_writer.py — V10：单章节写作模块。

负责为单个章节构建 prompt、调用 LLM、解析结果。
支持重试和状态追踪。LLM 调用方式与现有 zone_c_chain.py 保持一致（通过 subprocess 或文件保存/手动执行）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any

from models import (
    ChapterResult,
    ChapterStatus,
    ChapterTask,
    DecisionInput,
    DecisionOutput,
)
from template_parser import TemplateChapter
from scene_config import SceneConfig, get_scene_config


def write_chapter(
    task: ChapterTask,
    context: dict[str, Any],
    company_name: str = "",
    scene: SceneConfig | None = None,
    max_retries: int = 2,
) -> ChapterResult:
    """写单个章节（含重试循环）。

    Args:
        task: 章节任务定义。
        context: 数据上下文（已加载的 JSON 数据）。
        company_name: 公司名称。
        scene: 场景配置（温度、模型等）。
        max_retries: 最大重试次数。

    Returns:
        ChapterResult 对象。
    """
    if scene is None:
        scene = get_scene_config("write")

    result = ChapterResult(task=task)

    for attempt in range(max_retries + 1):
        result.retry_count = attempt
        result.status = ChapterStatus.WRITING

        prompt = _build_chapter_prompt(task, context, company_name)

        try:
            content = _call_llm(prompt, scene)
            if content:
                result.content = content
                result.status = ChapterStatus.PASSED
                # 提取证据项
                result.evidence_items = _extract_evidence_items(content)
                return result
        except Exception as e:
            result.error = str(e)

        if attempt < max_retries:
            print(f"    ⚠️ Ch{task.index:02d} 第{attempt+1}次尝试失败，重试中...")
        else:
            result.status = ChapterStatus.FAILED
            result.error = result.error or f"超过最大重试次数 {max_retries}"

    return result


def write_decision_chapter(
    decision_input: DecisionInput,
    scene: SceneConfig | None = None,
) -> DecisionOutput:
    """写投资决策章节。

    在所有分析章节完成后，综合各章关键指标生成 Continue/Hold/Abandon 判断。

    Args:
        decision_input: 决策综合的结构化输入。
        scene: 场景配置。

    Returns:
        DecisionOutput 对象。
    """
    if scene is None:
        scene = get_scene_config("decision")

    prompt = _build_decision_prompt(decision_input)

    try:
        content = _call_llm(prompt, scene)
        return _parse_decision_output(content, decision_input)
    except Exception as e:
        # 返回基于规则的 fallback 决策
        return _fallback_decision(decision_input, str(e))


# ---------------------------------------------------------------------------
# 内部：prompt 构建
# ---------------------------------------------------------------------------


def _build_chapter_prompt(task: ChapterTask, context: dict[str, Any], company_name: str) -> str:
    """为章节构建完整写作 prompt。

    Args:
        task: 章节任务。
        context: 数据上下文。
        company_name: 公司名称。

    Returns:
        完整 prompt 字符串。
    """
    parts: list[str] = []

    # 1. 写作指令
    parts.append("# 写作指令\n")
    parts.append(f"## 本章任务：{task.title}\n")
    parts.append("> 你拥有以下**全部数据文件**的完整上下文。请聚焦本章的写作合同，不要写其他章节的内容。\n")

    if task.chapter_goal:
        parts.append(f"### 本章目标\n{task.chapter_goal}\n")

    contract = task.chapter_contract
    if contract.get("narrative_mode"):
        parts.append(f"### 叙事模式：{contract['narrative_mode']}\n")

    if contract.get("must_answer"):
        parts.append("### 必须回答的问题")
        for i, q in enumerate(contract["must_answer"], 1):
            parts.append(f"{i}. {q}")
        parts.append("")

    if contract.get("must_not_cover"):
        parts.append("### 禁止涉及")
        for item in contract["must_not_cover"]:
            parts.append(f"- {item}")
        parts.append("")

    if contract.get("required_output_items"):
        parts.append("### 最低输出要求")
        for item in contract["required_output_items"]:
            parts.append(f"- {item}")
        parts.append("")

    # 证据引用规则
    parts.extend([
        "### 证据引用规则\n",
        "- 每个数据断言必须附带证据来源锚点：`[source: 文件名]`\n",
        "- 缺失数据标注 `⚠️ 数据不可用`，禁止编造数字\n",
        "- 金额单位：百万元 RMB（港股除外用 HKD）\n",
        "\n---\n",
    ])

    # 2. 章节模板骨架
    parts.append("## 章节模板\n")
    filled_skeleton = _fill_template_vars(task.skeleton, context, company_name)
    parts.append(filled_skeleton)
    parts.append("")

    # 3. 数据附录（仅本章需要的数据）
    data_text = _build_data_appendix(task, context)
    if data_text:
        parts.append("---\n")
        parts.append("## 数据附录\n")
        parts.append(data_text)

    return "\n".join(parts)


def _build_decision_prompt(di: DecisionInput) -> str:
    """构建决策综合 prompt。

    Args:
        di: 决策输入数据。

    Returns:
        决策 prompt 字符串。
    """
    return f"""# 投资决策综合

你是一位买方分析师。基于以下各章的客观分析结果，给出对该标的的最终投资决策。

## 分析摘要

| 维度 | 结果 |
|------|------|
| 公司 | {di.company_name}（{di.ts_code}） |
| 因子1A 快筛 | {di.factor_1a_summary} |
| 因子1B 定性（护城河等） | {di.factor_1b_summary} |
| 因子1C 增长质量 | {di.factor_1c_summary} |
| 因子2 穿透回报率（粗） | {di.factor_2_gg}% |
| 因子3 穿透回报率（精） | {di.factor_3_gg}%（基准），悲观 {di.factor_3_gg_scenarios.get('悲观', '?')}%，乐观 {di.factor_3_gg_scenarios.get('乐观', '?')}% |
| 因子4 DDM公允价 | {di.factor_4_ddm_v} |
| 当前股价 | {di.factor_4_current_price} |
| 建议仓位 | {di.factor_4_position_pct}% |
| II（门槛回报率） | {di.ii}% |
| Rf（无风险利率） | {di.rf}% |
| 否决门 | {di.rejection_status} |
| 护城河评级 | {di.moat_rating} |
| 关键风险 | {', '.join(di.key_risks) if di.key_risks else '未识别显著风险'} |

## 决策规则

- **Continue**：GG > II，DDM公允价显著高于当前价，护城河 ≥ Moderate，无否决门触发
- **Hold**：GG在II的0.5-1.0倍之间，或估值合理但存在不确定性
- **Abandon**：GG < II×0.5，或否决门触发，或护城河为None且无改善迹象

## 请以 JSON 格式输出你的判断

```json
{{
  "verdict": "Continue|Hold|Abandon",
  "confidence": "high|medium|low",
  "rationale": ["依据1", "依据2", "依据3"],
  "assumptions": [
    {{"assumption": "关键假设", "impact_if_wrong": "若错误的影响", "probability": "low|medium|high"}}
  ],
  "triggers": ["降级条件1", "降级条件2"],
  "exit_conditions": ["清仓条件1", "清仓条件2"]
}}
```"""


def _fill_template_vars(text: str, context: dict[str, Any], company_name: str) -> str:
    """替换模板中的基础变量。

    Args:
        text: 模板文本。
        context: 数据上下文。
        company_name: 公司名称。

    Returns:
        替换后的文本。
    """
    result = text
    meta = context.get("_meta", {})
    contract = context.get("analysis_contract", {})

    result = result.replace("{company_name}", company_name or str(contract.get("company_name", "?")))
    result = result.replace("{ts_code}", str(meta.get("ts_code", "?")))
    result = result.replace("{analysis_date}", datetime.now().strftime("%Y-%m-%d"))

    is_hk = ".HK" in str(meta.get("ts_code", ""))
    result = result.replace("{currency}", "HKD" if is_hk else "RMB")

    years = contract.get("effective_years", [2021, 2022, 2023, 2024, 2025])
    for i, year in enumerate(years[:5]):
        result = result.replace(f"{{fy_year_{i+1}}}", str(year))

    return result


def _build_data_appendix(task: ChapterTask, context: dict[str, Any]) -> str:
    """为章节构建数据附录（Dayu 模式：提供全部上下文）。

    Agent 拥有所有数据的访问权，CHAPTER_CONTRACT 约束写什么而非能看什么。
    仅排除明显的叙事字段（Zone J 的 moat_rating/summary/methodology_note）。

    Args:
        task: 章节任务。
        context: 完整数据上下文。

    Returns:
        JSON 格式的完整数据附录文本。
    """
    # 决策章和来源清单不需要原始数据
    if "决策" in task.title or "来源" in task.title:
        return ""

    # Zone J 文件需要剥离叙事
    _zone_j_files = {"moat_assessment", "capex_classification", "earnings_quality", "data_discount"}

    # 全部可用数据（排除内部元数据）
    available_keys = sorted(
        k for k, v in context.items()
        if not k.startswith("_") and not (isinstance(v, dict) and v.get("_missing"))
    )

    if not available_keys:
        return ""

    lines = [f"以下为本次分析的完整结构化数据（共 {len(available_keys)} 个文件）。", ""]
    for key in available_keys:
        data = context[key]
        if key in _zone_j_files:
            data = _strip_narrative(data)
        lines.append(f"### {key}")
        lines.append("```json")
        lines.append(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


_ZONE_J_STRIP_KEYS = {"moat_rating", "summary", "methodology_note"}


def _strip_narrative(data: dict) -> dict:
    """剥离 Zone J 输出中的叙事字段，只保留结构化参数。"""
    if not isinstance(data, dict):
        return data
    result = {}
    for k, v in data.items():
        if k in _ZONE_J_STRIP_KEYS:
            continue
        if isinstance(v, dict):
            result[k] = _strip_narrative(v)
        elif isinstance(v, list):
            result[k] = [_strip_narrative(i) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# 内部：LLM 调用
# ---------------------------------------------------------------------------


def _call_llm(prompt: str, scene: SceneConfig) -> str:
    """调用 LLM 生成章节内容。

    当前实现：将 prompt 写入临时文件，提示用户通过 Claude Code 处理。
    后续可替换为直接 API 调用。

    Args:
        prompt: 完整 prompt。
        scene: 场景配置。

    Returns:
        LLM 回复文本。

    Raises:
        RuntimeError: 当 LLM 调用失败时。
    """
    # 策略：将 prompt 保存到文件，由 write_pipeline.py 在 Claude Code 环境中处理
    # 在 Claude Code 上下文中，协调器 Read prompt → 传给 LLM → Write 结果
    # 此函数在 Claude Code 协调器模式下由外部驱动

    # 当前返回占位符——实际调用由 write_pipeline.py 协调
    raise RuntimeError(
        "chapter_writer._call_llm 需要由 write_pipeline 协调器在 Claude Code 环境中调用。"
        "请使用 write_pipeline.py 作为入口。"
    )


# ---------------------------------------------------------------------------
# 内部：结果解析
# ---------------------------------------------------------------------------


def _extract_evidence_items(content: str) -> list[str]:
    """从章节内容中提取证据锚点。

    Args:
        content: 章节 Markdown 内容。

    Returns:
        去重后的证据项列表。
    """
    import re
    pattern = re.compile(r"\[source:\s*([^\]]+)\]")
    matches = pattern.findall(content)
    # 去重保持顺序
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        m = m.strip()
        if m not in seen:
            seen.add(m)
            result.append(m)
    return result


def _parse_decision_output(content: str, di: DecisionInput) -> DecisionOutput:
    """从 LLM 输出中解析 DecisionOutput。

    Args:
        content: LLM 回复文本。
        di: 原始决策输入（用于 fallback）。

    Returns:
        DecisionOutput 对象。
    """
    import re

    # 尝试提取 JSON 块
    json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if not json_match:
        json_match = re.search(r"\{[\s\S]*\"verdict\"[\s\S]*\}", content)

    if json_match:
        try:
            data = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))
            return DecisionOutput(
                verdict=data.get("verdict", "Hold"),
                confidence=data.get("confidence", "medium"),
                rationale=data.get("rationale", []),
                assumptions=data.get("assumptions", []),
                triggers=data.get("triggers", []),
                exit_conditions=data.get("exit_conditions", []),
            )
        except (json.JSONDecodeError, KeyError):
            pass

    return _fallback_decision(di, "无法解析LLM输出")


def _fallback_decision(di: DecisionInput, reason: str) -> DecisionOutput:
    """基于规则的 fallback 决策（当 LLM 调用失败时）。

    Args:
        di: 决策输入数据。
        reason: 失败原因。

    Returns:
        DecisionOutput 对象。
    """
    # 基于 GG vs II 的简单规则
    if di.rejection_status and "触发" in di.rejection_status:
        verdict = "Abandon"
        confidence = "high"
    elif di.factor_3_gg > di.ii:
        verdict = "Continue"
        confidence = "medium"
    elif di.factor_3_gg > di.ii * 0.5:
        verdict = "Hold"
        confidence = "medium"
    else:
        verdict = "Abandon"
        confidence = "high"

    return DecisionOutput(
        verdict=verdict,
        confidence=confidence,
        rationale=[
            f"GG({di.factor_3_gg}%) vs II({di.ii}%)",
            f"DDM公允价 {di.factor_4_ddm_v} vs 当前价 {di.factor_4_current_price}",
            f"否决门: {di.rejection_status}",
            f"护城河: {di.moat_rating}",
            f"(基于规则的 fallback——{reason})",
        ],
        triggers=["GG < II 且无改善趋势", "否决门触发"],
        exit_conditions=["GG < Rf", "护城河评级降为 None", "管理层出现重大负面"],
    )
