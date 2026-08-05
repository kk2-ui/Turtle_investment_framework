#!/usr/bin/env python3
"""source_list_builder.py — V10：来源清单构建器。

汇总整份报告中的所有 [source: X] 证据锚点，去重后按类型归类，
生成格式化的来源清单章节。

从 Dayu 的 source_list_builder.py 裁剪而来：仅保留聚合和格式化功能。
"""

from __future__ import annotations

import os
import re
from typing import Any

from evidence_citation import EvidenceRegistry, _SOURCE_ANCHOR_PATTERN


def build_source_list(
    report_text: str,
    registry: EvidenceRegistry | None = None,
) -> str:
    """从报告文本中构建来源清单。

    Args:
        report_text: 报告 Markdown 全文。
        registry: 证据注册表（可选，用于获取来源描述）。

    Returns:
        格式化的来源清单 Markdown 文本。
    """
    if registry is None:
        registry = EvidenceRegistry()

    # 提取所有来源引用
    sources = registry.extract_canonical_sources(report_text)

    if not sources:
        return "## 来源清单\n\n_（未检测到证据引用）_\n"

    # 按类型分类
    categorized = _categorize_sources(sources, registry)

    lines = ["## 来源清单\n"]

    for category, items in categorized.items():
        lines.append(f"### {category}\n")
        for item in items:
            desc = registry.get_source_description(item)
            lines.append(f"- **{item}** — {desc}")
        lines.append("")

    # 添加统计
    lines.append(f"\n_共 {len(sources)} 个来源，{len(categorized)} 个类别_\n")

    return "\n".join(lines)


def build_source_list_from_chapters(
    chapter_results: dict[int, Any],
    registry: EvidenceRegistry | None = None,
) -> str:
    """从各章结果中构建来源清单。

    Args:
        chapter_results: 章节序号 → ChapterResult 的映射。
        registry: 证据注册表。

    Returns:
        格式化的来源清单 Markdown 文本。
    """
    if registry is None:
        registry = EvidenceRegistry()

    # 收集所有章节的证据项
    all_sources: list[str] = []
    for idx, result in sorted(chapter_results.items()):
        evidence_items = getattr(result, "evidence_items", [])
        if isinstance(result, dict):
            evidence_items = result.get("evidence_items", [])
        all_sources.extend(evidence_items)

    # 去重
    seen: set[str] = set()
    unique: list[str] = []
    for s in all_sources:
        if s not in seen:
            seen.add(s)
            unique.append(s)

    if not unique:
        return "## 来源清单\n\n_（各章未检测到证据引用）_\n"

    categorized = _categorize_sources(unique, registry)
    lines = ["## 来源清单\n"]

    for category, items in categorized.items():
        lines.append(f"### {category}\n")
        for item in items:
            desc = registry.get_source_description(item)
            lines.append(f"- **{item}** — {desc}")
        lines.append("")

    lines.append(f"\n_共 {len(unique)} 个来源，{len(categorized)} 个类别_\n")
    return "\n".join(lines)


def _categorize_sources(
    sources: list[str],
    registry: EvidenceRegistry,
) -> dict[str, list[str]]:
    """按类型对来源进行分类。

    Args:
        sources: 来源名称列表。
        registry: 证据注册表。

    Returns:
        类别名 → 来源列表的映射。
    """
    categories: dict[str, list[str]] = {
        "Zone A 定量计算": [],
        "Zone B 定性提取": [],
        "Zone J 判断参数": [],
        "年报原文": [],
        "其他": [],
    }

    for source in sources:
        if "compute_bundle" in source or "financial_trends" in source or "industry_context" in source:
            categories["Zone A 定量计算"].append(source)
        elif any(k in source for k in ["mda", "segments", "risks", "governance", "audit"]):
            categories["Zone B 定性提取"].append(source)
        elif any(k in source for k in ["moat_assessment", "capex_classification", "earnings_quality", "data_discount"]):
            categories["Zone J 判断参数"].append(source)
        elif "annual_report" in source or ".pdf" in source or re.match(r"20\d{2}_年报\.md$", source):
            categories["年报原文"].append(source)
        elif source in {"report_internal", "framework_method", "report_derivation", "public_market_research", "unresolved_evidence"}:
            categories["其他"].append(source)
        else:
            categories["其他"].append(source)

    # 移除空类别
    return {k: sorted(v) for k, v in categories.items() if v}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="构建来源清单")
    ap.add_argument("--report", help="报告文件路径")
    ap.add_argument("--output", help="输出目录")
    ap.add_argument("--code", help="股票代码")
    args = ap.parse_args()

    # 查找报告
    output_base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    report_path = args.report
    stock_dir = args.output

    if args.code:
        code_base = args.code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
        for name in os.listdir(output_base):
            if name.startswith(code_base) and os.path.isdir(os.path.join(output_base, name)):
                stock_dir = os.path.join(output_base, name)
                break

    if stock_dir and not report_path:
        for f in sorted(os.listdir(stock_dir), reverse=True):
            if f.endswith(".md") and ("v10" in f.lower() or "v7" in f.lower()):
                report_path = os.path.join(stock_dir, f)
                break

    if not report_path or not os.path.exists(report_path):
        print("ERROR: 找不到报告文件", file=sys.stderr)
        sys.exit(1)

    with open(report_path, encoding="utf-8") as f:
        text = f.read()

    registry = EvidenceRegistry()
    if stock_dir:
        registry.register_from_output_dir(stock_dir)

    source_list = build_source_list(text, registry)
    print(source_list)

    # 保存到文件
    if stock_dir:
        out_path = os.path.join(stock_dir, "source_list.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(source_list)
        print(f"✅ 已保存 → {out_path}")
