"""write_qualitative_pipeline.py — V12：定性章节 Prompt 生成器。

Phase Q.2: 加载统一模板，解析 Ch1-Ch9 定性章节，应用 facet 过滤，
为每个章节生成独立的写作 prompt 文件，供 Claude Code 在会话中处理。

不调用 LLM — 所有 prompt 由 Claude Code 通过内置 API 执行。

用法:
    python write_qualitative_pipeline.py --template report_template_v12.md \\
        --facets facets.json --context-dir ./output/XXXX \\
        --output-dir ./output/XXXX/qualitative
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 确保可导入 scripts 模块
_scripts_dir = str(Path(__file__).resolve().parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from scripts.company_facets import (
    CompanyFacetProfile,
    filter_chapter_contract_by_facets,
    filter_item_rules_by_facets,
    render_company_facets_for_prompt,
)
from scripts.template_parser import TemplateChapter, parse_template


def _read_json(path: str) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def build_master_qualitative_prompt(
    template_path: str,
    context_dir: str,
    output_dir: str,
    facets_path: str = "",
) -> str:
    """生成 Phase Q.2 主 prompt：包含所有定性章节的写作指令。

    返回一个完整的 Markdown prompt，Claude Code 可以直接按它逐章写入。
    """
    # 1. 加载模板
    template_text = Path(template_path).read_text(encoding="utf-8")
    layout = parse_template(template_text)
    facet_catalog = layout.facet_catalog

    qualitative = [ch for ch in layout.chapters if ch.part_label and "Part A" in ch.part_label]
    if not qualitative:
        return "❌ 模板中未找到 Part A 定性章节"

    # 2. 加载 facet
    company_facets: CompanyFacetProfile | None = None
    if facets_path and Path(facets_path).exists():
        raw = _read_json(facets_path)
        if raw:
            company_facets = CompanyFacetProfile.from_dict(raw)

    # 3. 加载上下文数据
    context: dict[str, Any] = {}
    for fname in ["financial_trends.json", "segments.json", "industry_context.json",
                   "compute_bundle.json", "analysis_contract.json", "mda.json",
                   "risks.json", "governance.json", "audit.json"]:
        data = _read_json(str(Path(context_dir) / fname))
        if data:
            context[fname.replace(".json", "")] = data

    # 4. 构建主 prompt
    sections: list[str] = []
    sections.append(f"""# Phase Q.2: 定性深度分析章节写作

请按顺序为以下 {len(qualitative)} 个定性分析章节逐一生成内容。每个章节写入独立文件到 `{output_dir}/chapters/_ch{{nn}}_{{title}}.md`。

## 全局上下文数据

```json
{json.dumps(context, ensure_ascii=False, indent=2, default=str)[:8000]}
```

## 公司 Facet 信息

{render_company_facets_for_prompt(company_facets)}

## 写作规范

- 每个章节必须包含三部分：「结论要点」「详细情况」「证据与出处」
- 使用 `[source: 文件名]` 格式标注数据来源
- 不要编造信息，基于提供的上下文数据
- 若信息不足，标注「未披露」或「未提取」

---

""")

    # 5. 为每个章节生成写作指令
    for ch in qualitative:
        # Facet 过滤
        contract = ch.chapter_contract
        rules = list(ch.item_rules)
        if company_facets:
            contract = filter_chapter_contract_by_facets(ch.chapter_contract, company_facets, facet_catalog=facet_catalog)
            rules = filter_item_rules_by_facets(ch.item_rules, company_facets, facet_catalog=facet_catalog)

        contract_dict = contract.to_dict() if contract else {}
        rules_list = [r.to_dict() for r in rules] if rules else []

        sections.append(f"""## 章节 {ch.index}: {ch.title}

**章节目标**: {ch.chapter_goal}

**写作合同**:
```json
{json.dumps(contract_dict, ensure_ascii=False, indent=2)}
```

**条件规则**:
```json
{json.dumps(rules_list, ensure_ascii=False, indent=2)}
```

**章节骨架**:
```
{ch.skeleton[:3000]}
```

**输出文件**: `{output_dir}/chapters/_ch{ch.index:02d}_{_safe_title(ch.title)}.md`

请按上述骨架和合同写入本章节内容（Markdown 格式）。包含「结论要点」「详细情况」「证据与出处」三部分。

---

""")

    sections.append(f"""
## 完成检查

全部 {len(qualitative)} 个章节写完后，请确认：
- [ ] 每个章节文件已写入对应路径
- [ ] 每章包含「结论要点」「详细情况」「证据与出处」三部分
- [ ] 关键数据断言附带了 `[source: X]` 锚点
- [ ] 无占位符残留

然后写入 `{output_dir}/qualitative_manifest.json`:
```json
{{"run_type": "qualitative_v12", "chapters_total": {len(qualitative)}, "chapters_passed": {len(qualitative)}}}
```
""")

    return "\n".join(sections)


def _safe_title(title: str) -> str:
    """生成安全的文件名片段。"""
    return title.replace("/", "_").replace(" ", "_").replace("：", "_").replace(":", "_")[:40]


def main() -> None:
    ap = argparse.ArgumentParser(description="V12 定性章节 Prompt 生成器")
    ap.add_argument("--template", required=True, help="统一模板文件路径")
    ap.add_argument("--facets", default="", help="facets.json 路径")
    ap.add_argument("--context-dir", required=True, help="上下文数据目录")
    ap.add_argument("--output-dir", required=True, help="定性章节输出目录")
    ap.add_argument("--output-prompt", help="输出主 prompt 文件路径（默认 stdout）")
    args = ap.parse_args()

    # 确保输出目录存在
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    Path(args.output_dir, "chapters").mkdir(parents=True, exist_ok=True)

    prompt = build_master_qualitative_prompt(
        template_path=args.template,
        context_dir=args.context_dir,
        output_dir=args.output_dir,
        facets_path=args.facets,
    )

    if args.output_prompt:
        Path(args.output_prompt).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_prompt).write_text(prompt, encoding="utf-8")
        print(f"✅ 定性写作主 prompt → {args.output_prompt} ({len(prompt)} chars)")
    else:
        print(prompt)


if __name__ == "__main__":
    main()
