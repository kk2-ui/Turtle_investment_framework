#!/usr/bin/env python3
"""template_validator.py — V10：报告模板预检查工具。

验证模板文件的结构完整性：
- 至少包含必需章节
- 所有 CHAPTER_CONTRACT YAML 合法
- 所有 ITEM_RULE YAML 合法
- 骨架文本无残留 HTML 注释
"""

from __future__ import annotations

import argparse
import re
import sys

from template_parser import parse_template, TemplateLayout

# V10 必需章节标题（部分匹配即可）
_REQUIRED_CHAPTERS = [
    "报告元信息",
    "Executive Summary",
    "财务趋势",
    "因子1A/1B/1C",
    "因子2/3",
    "因子4",
    "投资决策",
]


def validate_template(layout: TemplateLayout) -> list[str]:
    """验证模板结构，返回问题列表（空列表 = 通过）。

    Args:
        layout: 解析后的模板结构。

    Returns:
        问题描述列表。
    """
    issues: list[str] = []

    # 1. 检查全文目标
    if not layout.report_goal:
        issues.append("缺少 REPORT_GOAL")

    # 2. 检查必需章节
    chapter_titles = [ch.title for ch in layout.chapters]
    for required in _REQUIRED_CHAPTERS:
        found = any(required in title for title in chapter_titles)
        if not found:
            issues.append(f"缺少必需章节: {required}")

    # 3. 检查每章的骨架是否残留 HTML 注释
    html_comment_pat = re.compile(r"<!--")
    for ch in layout.chapters:
        if html_comment_pat.search(ch.skeleton):
            issues.append(f"章节 {ch.title!r} 的骨架残留 HTML 注释")

    # 4. 检查 CHAPTER_CONTRACT 完整性
    for ch in layout.chapters:
        c = ch.chapter_contract
        # 至少 mode + answer 或 output_items 二选一
        if c.narrative_mode and not c.must_answer and not c.required_output_items:
            issues.append(
                f"章节 {ch.title!r}: CHAPTER_CONTRACT 有 narrative_mode 但无 must_answer 或 required_output_items"
            )

    # 5. 检查 ITEM_RULE 绑定
    for ch in layout.chapters:
        for rule in ch.item_rules:
            if not rule.target_heading:
                issues.append(f"章节 {ch.title!r}: ITEM_RULE '{rule.item}' 未绑定到任何标题")

    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description="验证报告模板结构")
    ap.add_argument("template", help="模板文件路径")
    ap.add_argument("--quiet", "-q", action="store_true", help="静默模式（仅输出错误）")
    args = ap.parse_args()

    with open(args.template, encoding="utf-8") as f:
        md = f.read()

    try:
        layout = parse_template(md)
    except ValueError as e:
        print(f"❌ 模板解析失败: {e}", file=sys.stderr)
        return 1

    issues = validate_template(layout)

    if issues:
        print(f"❌ 模板验证失败 ({len(issues)} 个问题):", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"✅ 模板验证通过")
        print(f"   章节数: {len(layout.chapters)}")
        print(f"   有合约的章节: {sum(1 for ch in layout.chapters if ch.chapter_contract.narrative_mode)}/{len(layout.chapters)}")
        print(f"   有规则的章节: {sum(1 for ch in layout.chapters if ch.item_rules)}/{len(layout.chapters)}")
        all_rules = sum(len(ch.item_rules) for ch in layout.chapters)
        print(f"   总规则数: {all_rules}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
