"""infer_company_facets.py — V12：公司 Facet 归因 Prompt 生成器。

Phase Q.1: 读取公司数据 + facet 候选词表，生成 facet 归因 prompt。
不调用 LLM — prompt 由 Claude Code 在会话中处理。

用法:
    python infer_company_facets.py --trends financial_trends.json \\
        --segments segments.json --catalog report_template_v12.md \\
        --output-prompt /tmp/facet_prompt.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保可导入 scripts 模块
_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from scripts.template_parser import parse_company_facet_catalog


def build_facet_prompt(
    company_data_text: str,
    facet_catalog: dict[str, list[str]],
) -> str:
    """构建 facet 归因 prompt。

    Args:
        company_data_text: 公司数据文本。
        facet_catalog: 候选词表 {"business_model_candidates": [...], "constraint_candidates": [...]}。

    Returns:
        Markdown 格式的 prompt，供 Claude Code 处理。
    """
    business = facet_catalog.get("business_model_candidates", [])
    constraints = facet_catalog.get("constraint_candidates", [])

    return f"""# Phase Q.1: 公司 Facet 归因

请根据以下公司信息，将其归类到候选业务类型和关键约束标签中。

## 候选词表

### 主业务类型（最多选 3 个，按置信度降序）
{chr(10).join(f'- {b}' for b in business)}

### 关键约束（最多选 3 个，按置信度降序）
{chr(10).join(f'- {c}' for c in constraints)}

## 公司数据

{company_data_text}

## 任务

请输出如下 JSON 到 `{{output_dir}}/qualitative/facets.json`（不要输出其他文本，纯 JSON）：

```json
{{
  "primary_facets": ["选中的业务类型1", "选中的业务类型2"],
  "cross_cutting_facets": ["选中的约束1"],
  "confidence_notes": "一句话说明归因依据"
}}
```

注意：
- primary_facets 必须从主业务类型候选词表中选取
- cross_cutting_facets 必须从关键约束候选词表中选取
- 如果某个维度无法确定，可以只选 1-2 个
"""


def build_company_data_text(
    trends_path: str = "",
    segments_path: str = "",
    industry_path: str = "",
) -> str:
    """从 JSON 文件中提取公司关键数据文本。"""
    parts: list[str] = []

    for path, label in [
        (trends_path, "财务趋势"),
        (segments_path, "业务分部"),
        (industry_path, "行业定位"),
    ]:
        if path and Path(path).exists():
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                text = _format_json_snippet(data, label)
                if text:
                    parts.append(text)
            except (json.JSONDecodeError, OSError):
                pass

    if not parts:
        return "（未提供公司数据）"
    return "\n\n".join(parts)


def _format_json_snippet(data: dict, label: str) -> str:
    """将 JSON 数据格式化为简短摘要。"""
    text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    # 截断过长的数据
    if len(text) > 3000:
        text = text[:3000] + "\n... (truncated)"
    return f"### {label}\n```json\n{text}\n```"


def main() -> None:
    ap = argparse.ArgumentParser(description="V12 Facet 归因 Prompt 生成器")
    ap.add_argument("--trends", default="", help="financial_trends.json 路径")
    ap.add_argument("--segments", default="", help="segments.json 路径")
    ap.add_argument("--industry", default="", help="industry_context.json 路径")
    ap.add_argument("--catalog", required=True, help="模板文件路径")
    ap.add_argument("--output-prompt", help="输出 prompt 文件路径（默认 stdout）")
    args = ap.parse_args()

    # 加载 catalog
    template_text = Path(args.catalog).read_text(encoding="utf-8")
    facet_catalog = parse_company_facet_catalog(template_text)

    # 组装公司数据
    company_data = build_company_data_text(
        trends_path=args.trends,
        segments_path=args.segments,
        industry_path=args.industry,
    )

    # 生成 prompt
    prompt = build_facet_prompt(company_data, facet_catalog)

    if args.output_prompt:
        out_path = Path(args.output_prompt)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(prompt, encoding="utf-8")
        print(f"✅ Facet prompt → {out_path} ({len(prompt)} chars)")
    else:
        print(prompt)


if __name__ == "__main__":
    main()
