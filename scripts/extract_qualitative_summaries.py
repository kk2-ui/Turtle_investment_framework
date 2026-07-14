"""extract_qualitative_summaries.py — V12：定性摘要提取 Prompt 生成器。

Phase Q.3: 读取 Phase Q.2 产出的定性章节 MD 文件，
生成结构化摘要提取 prompt，供 Claude Code 处理后得到 qualitative_summary.json。

不调用 LLM — prompt 由 Claude Code 通过内置 API 执行。

用法:
    python extract_qualitative_summaries.py --chapters-dir ./output/XXXX/qualitative/chapters \\
        --output-prompt /tmp/extract_prompt.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_extraction_prompt(chapters_dir: str, output_path: str) -> str:
    """构建定性摘要提取 prompt。

    Args:
        chapters_dir: 定性章节 MD 文件目录。
        output_path: qualitative_summary.json 输出路径。

    Returns:
        Markdown 格式的 prompt。
    """
    chapters_path = Path(chapters_dir)
    if not chapters_path.exists():
        return "❌ 定性章节目录不存在"

    md_files = sorted(chapters_path.glob("_ch*.md"))
    if not md_files:
        return "❌ 未找到定性章节文件"

    # 组装章节内容
    chapter_parts: list[str] = []
    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        truncated = content[:3000] if len(content) > 3000 else content
        chapter_parts.append(f"### {md_file.stem}\n\n{truncated}")

    chapters_text = "\n\n---\n\n".join(chapter_parts)

    return f"""# Phase Q.3: 定性章节结构化摘要提取

请阅读以下 {len(md_files)} 个定性分析章节，提取结构化摘要供 Turtle Zone J 定量参数估计使用。

## 定性章节内容

{chapters_text}

## 提取任务

请输出如下 JSON 到 `{output_path}`（纯 JSON，不要 markdown 包裹）：

```json
{{
  "ch3_business_model": {{
    "moat_rating": "Strong/Moderate/Weak/None",
    "moat_sources": ["护城河来源1", "护城河来源2"],
    "moat_evidence_summary": "护城河证据摘要（最多200字）",
    "b_class_segments": [{{"name": "业务名称", "revenue_pct": 30, "classification": "B-劣/B-中/A"}}],
    "b_penalty_evidence": "b_penalty 相关证据摘要",
    "g_base_context": "增长驱动力上下文（用于估算 g_base 参数）",
    "key_constraints": ["关键约束1", "关键约束2"]
  }},
  "ch5_operating_performance": {{
    "revenue_drivers": ["驱动1", "驱动2"],
    "growth_quality": "high/medium/low",
    "structural_vs_cyclical": "structural/mixed/cyclical",
    "incremental_roic_context": "增量ROIC相关上下文",
    "data_credibility_notes": "数据可信度备注"
  }},
  "ch6_financial_performance": {{
    "earnings_quality": "high/medium/low",
    "earnings_quality_notes": "盈利质量说明",
    "cashflow_quality": "high/medium/low",
    "non_recurring_items": ["非经常项1"],
    "capital_allocation_quality": "good/neutral/poor",
    "capital_allocation_notes": "资本配置判断"
  }},
  "ch8_governance": {{
    "governance_rating": "strong/adequate/weak",
    "key_concerns": ["治理关注点"],
    "incentive_alignment": "good/neutral/poor",
    "data_discount_signals": ["数据折扣信号"]
  }},
  "ch9_risks": {{
    "veto_level_risks": [{{"risk": "否决级风险", "trigger": "触发条件", "impact": "影响"}}],
    "major_concerns": ["重大关注"],
    "trackable_indicators": ["跟踪指标"]
  }}
}}
```

## 注意事项
- 严格基于提供的章节内容，不编造信息
- 如果某字段信息不足，填 "未提取" 或空列表 `[]`
- 护城河评级和盈利质量评级必须有对应的章节证据支撑
- b_class_segments 中的 revenue_pct 必须是百分比数字
- g_base_context 和 b_penalty_evidence 对后续定量分析至关重要，请尽可能详细
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="V12 定性摘要提取 Prompt 生成器")
    ap.add_argument("--chapters-dir", required=True, help="定性章节目录（含 _ch*.md）")
    ap.add_argument("--output-path", default="qualitative_summary.json", help="摘要 JSON 输出路径")
    ap.add_argument("--output-prompt", help="输出 prompt 文件路径（默认 stdout）")
    args = ap.parse_args()

    prompt = build_extraction_prompt(args.chapters_dir, args.output_path)

    if args.output_prompt:
        Path(args.output_prompt).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_prompt).write_text(prompt, encoding="utf-8")
        print(f"✅ 摘要提取 prompt → {args.output_prompt} ({len(prompt)} chars)")
    else:
        print(prompt)


if __name__ == "__main__":
    main()
