#!/usr/bin/env python3
"""template_parser.py — V12：报告模板解析模块。

将统一报告模板解析为 TemplateLayout，提取：
- 全文目标（REPORT_GOAL）、读者画像（AUDIENCE_PROFILE）
- 公司 Facet 候选词表（COMPANY_FACET_CATALOG）—— V12 新增
- 章节列表（每个 ## 一级标题为一个章节）
- 每章的 CHAPTER_GOAL、CHAPTER_CONTRACT（含 preferred_lens）、ITEM_RULE（含 facets_any）、骨架

V12 变更：
- 从 models.py 导入 ChapterContract/ItemRule/PreferredLens（替代本地定义）
- CHAPTER_CONTRACT 新增 preferred_lens 字段解析
- ITEM_RULE 新增 facets_any 字段解析
- 新增 COMPANY_FACET_CATALOG 提取与解析
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from typing import Any

import yaml

from scripts.models import ChapterContract, ItemRule, PreferredLens

_HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_COMMENT_BODY_PATTERN = re.compile(r"<!--(.*?)-->", re.DOTALL)
_REPORT_GOAL_START = "REPORT_GOAL"
_REPORT_GOAL_END = "END_REPORT_GOAL"
_AUDIENCE_PROFILE_START = "AUDIENCE_PROFILE"
_AUDIENCE_PROFILE_END = "END_AUDIENCE_PROFILE"
_CHAPTER_GOAL_START = "CHAPTER_GOAL"
_CHAPTER_GOAL_END = "END_CHAPTER_GOAL"
_CHAPTER_CONTRACT_START = "CHAPTER_CONTRACT"
_CHAPTER_CONTRACT_END = "END_CHAPTER_CONTRACT"
_ITEM_RULE_START = "ITEM_RULE"
_ITEM_RULE_END = "END_ITEM_RULE"
# V12 新增：Facet Catalog
_FACET_CATALOG_START = "COMPANY_FACET_CATALOG"
_FACET_CATALOG_END = "END_COMPANY_FACET_CATALOG"

# CHAPTER_CONTRACT 支持的字段（V12：新增 preferred_lens）
_CONTRACT_KEYS = {
    "narrative_mode",
    "must_answer",
    "must_not_cover",
    "required_output_items",
    "preferred_lens",
}

# preferred_lens 支持的优先级
_SUPPORTED_LENS_PRIORITIES = {"core", "supporting"}


@dataclass
class TemplateChapter:
    """模板章节对象。

    Args:
        index: 章节序号（从 1 开始）。
        title: 章节标题（## 后的文本）。
        content: 章节完整文本（含 HTML 注释）。
        chapter_goal: 本章回答的总目标。
        skeleton: 去除 HTML 注释后的章节骨架。
        chapter_contract: 章节级写作合同。
        item_rules: 条件型条目规则列表。
        part_label: 章节所属分区标签（如 "Part A: 定性深度分析"），V12 新增。
    """

    index: int
    title: str
    content: str
    chapter_goal: str
    skeleton: str
    chapter_contract: ChapterContract
    item_rules: list[ItemRule]
    part_label: str = ""


@dataclass
class TemplateLayout:
    """模板结构对象。

    Args:
        report_goal: 全文总目标。
        audience_profile: 全局读者画像。
        facet_catalog: 公司 Facet 候选词表（V12 新增）。
        preface: 第一章前导文本（原始，含 HTML 注释）。
        preface_skeleton: 前导文本剔除 HTML 注释后的骨架。
        chapters: 一级章节列表。
    """

    report_goal: str
    audience_profile: str
    facet_catalog: dict[str, list[str]]
    preface: str
    preface_skeleton: str
    chapters: list[TemplateChapter]


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def parse_template(template_markdown: str) -> TemplateLayout:
    """解析模板 Markdown 为 TemplateLayout。

    Args:
        template_markdown: 模板全文。

    Returns:
        TemplateLayout 对象。

    Raises:
        ValueError: 当模板缺少一级章节（## ）时抛出。
    """
    lines = template_markdown.splitlines()
    heading_positions: list[int] = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            heading_positions.append(i)

    if not heading_positions:
        raise ValueError("模板中未找到一级章节（## ）")

    # 前导文本：第一个 ## 之前的所有内容
    preface = "\n".join(lines[: heading_positions[0]]).strip()

    # 提取全文目标
    report_goal = _extract_text_block(preface, _REPORT_GOAL_START, _REPORT_GOAL_END, allow_empty=True)
    # 提取读者画像
    audience_profile = _extract_text_block(preface, _AUDIENCE_PROFILE_START, _AUDIENCE_PROFILE_END, allow_empty=True)
    # V12 新增：提取公司 Facet 候选词表
    facet_catalog = _extract_facet_catalog(preface)
    # 前导骨架（去注释）
    preface_skeleton = _strip_html_comments(preface).strip()

    # 解析章节
    chapters: list[TemplateChapter] = []
    current_part_label = ""
    for pos_idx, start_line in enumerate(heading_positions):
        end_line = heading_positions[pos_idx + 1] if pos_idx + 1 < len(heading_positions) else len(lines)
        section_lines = lines[start_line:end_line]
        content = "\n".join(section_lines).strip()
        title = section_lines[0][3:].strip()  # 去掉 "## "

        # V12：检测 Part 分区标题（如 "Part A: 定性深度分析"）
        if _is_part_header(title):
            current_part_label = title
            continue

        chapter_goal = _extract_text_block(content, _CHAPTER_GOAL_START, _CHAPTER_GOAL_END, allow_empty=True)
        skeleton = _strip_html_comments(content).strip()
        chapter_contract = _extract_chapter_contract(content, chapter_title=title)
        item_rules = _extract_item_rules(content, chapter_title=title)

        chapters.append(
            TemplateChapter(
                index=len(chapters) + 1,
                title=title,
                content=content,
                chapter_goal=chapter_goal,
                skeleton=skeleton,
                chapter_contract=chapter_contract,
                item_rules=item_rules,
                part_label=current_part_label,
            )
        )

    return TemplateLayout(
        report_goal=report_goal,
        audience_profile=audience_profile,
        facet_catalog=facet_catalog,
        preface=preface,
        preface_skeleton=preface_skeleton,
        chapters=chapters,
    )


def build_report_markdown(preface: str, chapters: list[str]) -> str:
    """按模板顺序拼接报告正文。

    Args:
        preface: 前导文本（如报告标题行）。
        chapters: 已完成章节正文列表（每项需含 ## 标题）。

    Returns:
        报告 Markdown 全文。

    Raises:
        ValueError: 当章节列表为空时抛出。
    """
    if not chapters:
        raise ValueError("至少需要一个章节内容")

    body = "\n\n---\n\n".join(chapter.strip() for chapter in chapters if chapter.strip())
    if preface:
        return f"{preface.strip()}\n\n---\n\n{body}".strip()
    return body.strip()


def parse_company_facet_catalog(template_markdown: str) -> dict[str, list[str]]:
    """从模板全文中提取公司 Facet 候选词表。

    这是 parse_template 中 facet 提取逻辑的独立版本，
    方便在不完整解析模板时单独提取 facet 目录。

    Args:
        template_markdown: 模板全文。

    Returns:
        {"business_model_candidates": [...], "constraint_candidates": [...]}。
    """
    return _extract_facet_catalog(template_markdown)


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


def _is_part_header(title: str) -> bool:
    """判断章节标题是否为 Part 分区标题（如 "Part A: 定性深度分析"）。

    Part 标题本身不是章节，不产生 ChapterTask。
    """
    return bool(re.match(r"^Part\s+[A-Z]:", title))


def _strip_html_comments(text: str) -> str:
    """删除 HTML 注释块，保留非注释内容。"""
    normalized = text.replace("\r\n", "\n")
    lines = normalized.split("\n")
    in_comment = False
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        if stripped.startswith("<!--"):
            in_comment = True
            continue
        if in_comment:
            if "-->" in stripped:
                in_comment = False
            continue
        cleaned = _HTML_COMMENT_PATTERN.sub("", line)
        kept.append(cleaned)
    return "\n".join(kept)


def _extract_text_block(
    raw_text: str,
    start_marker: str,
    end_marker: str,
    *,
    allow_empty: bool = False,
) -> str:
    """从 HTML 注释中提取命名文本块。"""
    payloads: list[str] = []
    for match in _HTML_COMMENT_BODY_PATTERN.finditer(raw_text):
        body = match.group(1)
        payload = _extract_from_comment_body(body, start_marker, end_marker)
        if payload is not None:
            payloads.append(payload)

    if not payloads:
        if allow_empty:
            return ""
        raise ValueError(f"缺少 {start_marker} 块")
    if len(payloads) > 1:
        raise ValueError(f"存在多个 {start_marker} 块")
    return payloads[0]


def _extract_from_comment_body(comment_body: str, start_marker: str, end_marker: str) -> str | None:
    """从单个 HTML 注释体中提取命名标记间的文本。"""
    lines = [line.rstrip() for line in comment_body.splitlines()]
    start_idx: int | None = None
    for i, line in enumerate(lines):
        if line.strip() == start_marker:
            start_idx = i
            break
    if start_idx is None:
        return None
    for i in range(start_idx + 1, len(lines)):
        if lines[i].strip() == end_marker:
            payload = textwrap.dedent("\n".join(lines[start_idx + 1 : i])).strip()
            if not payload:
                raise ValueError(f"{start_marker} 块不能为空")
            return payload
    raise ValueError(f"{start_marker} 缺少结束标记 {end_marker}")


# ---------------------------------------------------------------------------
# V12 新增：COMPANY_FACET_CATALOG 提取
# ---------------------------------------------------------------------------


def _extract_facet_catalog(raw_text: str) -> dict[str, list[str]]:
    """从模板前导文本中提取 COMPANY_FACET_CATALOG。

    返回 {"business_model_candidates": [...], "constraint_candidates": [...]}。
    若模板中缺少 FACET_CATALOG 块，返回空列表。
    """
    try:
        payload = _extract_text_block(raw_text, _FACET_CATALOG_START, _FACET_CATALOG_END, allow_empty=True)
    except ValueError:
        return {"business_model_candidates": [], "constraint_candidates": []}

    if not payload:
        return {"business_model_candidates": [], "constraint_candidates": []}

    try:
        raw = yaml.safe_load(payload)
    except yaml.YAMLError:
        return {"business_model_candidates": [], "constraint_candidates": []}

    if not isinstance(raw, dict):
        return {"business_model_candidates": [], "constraint_candidates": []}

    business = _parse_string_list_value(raw.get("business_model_candidates", []))
    constraints = _parse_string_list_value(raw.get("constraint_candidates", []))
    return {
        "business_model_candidates": business,
        "constraint_candidates": constraints,
    }


# ---------------------------------------------------------------------------
# CHAPTER_CONTRACT 提取（V12 扩展：preferred_lens）
# ---------------------------------------------------------------------------


def _extract_chapter_contract(chapter_content: str, *, chapter_title: str) -> ChapterContract:
    """从章节原文中提取 CHAPTER_CONTRACT。

    V12: 新增 preferred_lens 字段解析。
    """
    payloads: list[str] = []
    for match in _HTML_COMMENT_BODY_PATTERN.finditer(chapter_content):
        body = match.group(1)
        payload = _extract_from_comment_body(body, _CHAPTER_CONTRACT_START, _CHAPTER_CONTRACT_END)
        if payload is not None:
            payloads.append(payload)

    if not payloads:
        return ChapterContract.empty()
    if len(payloads) > 1:
        raise ValueError(f"章节 {chapter_title!r} 存在多个 CHAPTER_CONTRACT")

    try:
        raw = yaml.safe_load(payloads[0])
    except yaml.YAMLError as e:
        raise ValueError(f"章节 {chapter_title!r} 的 CHAPTER_CONTRACT YAML 非法: {e}") from e

    if not isinstance(raw, dict):
        raise ValueError(f"章节 {chapter_title!r} 的 CHAPTER_CONTRACT 必须解析为映射")

    # 校验字段
    unexpected = sorted(set(raw.keys()) - _CONTRACT_KEYS)
    if unexpected:
        raise ValueError(
            f"章节 {chapter_title!r} 的 CHAPTER_CONTRACT 包含未支持字段: {', '.join(unexpected)}"
        )

    narrative_mode = str(raw.get("narrative_mode", "")).strip()
    must_answer = _parse_string_list(raw.get("must_answer", []), "must_answer", chapter_title)
    must_not_cover = _parse_string_list(raw.get("must_not_cover", []), "must_not_cover", chapter_title)
    required_output_items = _parse_string_list(raw.get("required_output_items", []), "required_output_items", chapter_title)
    # V12 新增
    preferred_lens = _parse_preferred_lens(raw.get("preferred_lens", []), chapter_title=chapter_title)

    return ChapterContract(
        narrative_mode=narrative_mode,
        must_answer=must_answer,
        must_not_cover=must_not_cover,
        required_output_items=required_output_items,
        preferred_lens=preferred_lens,
    )


def _parse_preferred_lens(value: Any, *, chapter_title: str) -> list[PreferredLens]:
    """解析 preferred_lens 字段为 PreferredLens 对象列表。

    支持两种格式：
    1. 新格式（推荐）：对象列表 [{lens, priority, facets_any}, ...]
    2. 旧格式（兼容）：映射 {group_name: [lens_items, ...]}
    """
    if value is None:
        return []

    if isinstance(value, dict):
        # 旧映射格式 → 转换为对象列表
        normalized: list[PreferredLens] = []
        for group_name, lens_items in value.items():
            if not isinstance(group_name, str) or not isinstance(lens_items, list):
                raise ValueError(
                    f"章节 {chapter_title!r} 的 preferred_lens 映射格式非法：键必须为字符串，值必须为列表"
                )
            priority = "core" if group_name.strip() == "default" else "supporting"
            for item in lens_items:
                if not isinstance(item, str):
                    raise ValueError(f"章节 {chapter_title!r} 的 preferred_lens 项必须为字符串")
                normalized.append(PreferredLens(lens=item.strip(), priority=priority))
        return normalized

    if not isinstance(value, list):
        raise ValueError(f"章节 {chapter_title!r} 的 preferred_lens 必须为对象列表或映射")

    # 新对象列表格式
    normalized: list[PreferredLens] = []
    for idx, raw_lens in enumerate(value):
        if not isinstance(raw_lens, dict):
            raise ValueError(f"章节 {chapter_title!r} 的 preferred_lens[{idx}] 必须为映射")
        expected_keys = {"lens", "priority", "facets_any"}
        unexpected_keys = sorted(set(raw_lens.keys()) - expected_keys)
        if unexpected_keys:
            raise ValueError(
                f"章节 {chapter_title!r} 的 preferred_lens[{idx}] 包含未支持字段: {', '.join(unexpected_keys)}"
            )
        lens_text = str(raw_lens.get("lens", "")).strip()
        if not lens_text:
            raise ValueError(f"章节 {chapter_title!r} 的 preferred_lens[{idx}].lens 不能为空")
        priority = str(raw_lens.get("priority", "core")).strip()
        if priority not in _SUPPORTED_LENS_PRIORITIES:
            raise ValueError(
                f"章节 {chapter_title!r} 的 preferred_lens[{idx}].priority={priority!r} 不支持"
            )
        facets_any = _parse_string_list_value(raw_lens.get("facets_any", []))
        normalized.append(PreferredLens(lens=lens_text, priority=priority, facets_any=facets_any))
    return normalized


# ---------------------------------------------------------------------------
# ITEM_RULE 提取（V12 扩展：facets_any）
# ---------------------------------------------------------------------------


def _extract_item_rules(chapter_content: str, *, chapter_title: str) -> list[ItemRule]:
    """从章节原文中提取全部 ITEM_RULE。

    V12: 新增 facets_any 字段解析。
    """
    heading_pat = re.compile(r"^(#{2,6})\s+(.*\S)\s*$", re.MULTILINE)
    rules: list[ItemRule] = []

    for match in _HTML_COMMENT_PATTERN.finditer(chapter_content):
        body = _HTML_COMMENT_BODY_PATTERN.match(match.group(0))
        if not body:
            continue
        payload = _extract_from_comment_body(body.group(1), _ITEM_RULE_START, _ITEM_RULE_END)
        if payload is None:
            continue

        try:
            raw = yaml.safe_load(payload)
        except yaml.YAMLError as e:
            raise ValueError(f"章节 {chapter_title!r} 的 ITEM_RULE YAML 非法: {e}") from e

        if not isinstance(raw, dict):
            raise ValueError(f"章节 {chapter_title!r} 的 ITEM_RULE 必须解析为映射")

        mode = str(raw.get("mode", "")).strip()
        item = str(raw.get("item", "")).strip()
        when = str(raw.get("when", "")).strip()
        # V12 新增
        facets_any = _parse_string_list_value(raw.get("facets_any", []))

        if not mode or not item:
            raise ValueError(f"章节 {chapter_title!r} 的 ITEM_RULE 缺少 mode 或 item")
        if mode not in ("conditional", "optional"):
            raise ValueError(f"章节 {chapter_title!r} 的 ITEM_RULE mode={mode!r} 不支持")

        # 查找该注释之前的最近标题
        prefix = chapter_content[: match.start()]
        target_heading = ""
        for hm in heading_pat.finditer(prefix):
            target_heading = hm.group(2).strip()

        rules.append(ItemRule(
            mode=mode,
            target_heading=target_heading,
            item=item,
            when=when,
            facets_any=facets_any,
        ))

    return rules


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _parse_string_list(value: Any, field_name: str, chapter_title: str) -> list[str]:
    """解析字符串列表字段。"""
    if not isinstance(value, list):
        raise ValueError(f"章节 {chapter_title!r} 的 CHAPTER_CONTRACT.{field_name} 必须为列表")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"章节 {chapter_title!r} 的 CHAPTER_CONTRACT.{field_name} 每项必须为字符串")
        stripped = item.strip()
        if stripped:
            result.append(stripped)
    return result


def _parse_string_list_value(value: Any) -> list[str]:
    """宽松解析字符串列表，返回去重后的非空字符串列表。"""
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            stripped = item.strip()
            if stripped not in result:
                result.append(stripped)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="解析报告模板")
    ap.add_argument("template", help="模板文件路径")
    ap.add_argument("--validate", action="store_true", help="仅验证，不输出解析结果")
    args = ap.parse_args()

    with open(args.template, encoding="utf-8") as f:
        md = f.read()

    try:
        layout = parse_template(md)
    except ValueError as e:
        print(f"❌ 模板解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    if args.validate:
        print(f"✅ 模板验证通过：{len(layout.chapters)} 个章节")
        bc = len(layout.facet_catalog.get("business_model_candidates", []))
        cc = len(layout.facet_catalog.get("constraint_candidates", []))
        print(f"   Facet候选: {bc} 种业务类型 + {cc} 种约束")
        for ch in layout.chapters:
            contract_info = ""
            if ch.chapter_contract.narrative_mode:
                contract_info = f" [合约: {ch.chapter_contract.narrative_mode}]"
            lens_info = f" ({len(ch.chapter_contract.preferred_lens)} lenses)" if ch.chapter_contract.preferred_lens else ""
            rules_info = f" ({len(ch.item_rules)} 条规则)" if ch.item_rules else ""
            part_info = f" [{ch.part_label}]" if ch.part_label else ""
            print(f"  {ch.index}. {ch.title}{part_info}{contract_info}{lens_info}{rules_info}")
        sys.exit(0)

    # 输出解析摘要
    print(f"Report Goal: {layout.report_goal[:80]}...")
    print(f"Audience: {layout.audience_profile[:80]}...")
    print(f"Facet Catalog: {len(layout.facet_catalog.get('business_model_candidates', []))} business + {len(layout.facet_catalog.get('constraint_candidates', []))} constraints")
    print(f"Chapters: {len(layout.chapters)}")
    for ch in layout.chapters:
        print(f"  [{ch.index}] {ch.title}")
        print(f"      Goal: {ch.chapter_goal[:60]}..." if ch.chapter_goal else "      Goal: (none)")
        print(f"      Skeleton: {len(ch.skeleton)} chars")
        if ch.chapter_contract.narrative_mode:
            print(f"      Contract: {ch.chapter_contract.narrative_mode}")
            print(f"      Lenses: {len(ch.chapter_contract.preferred_lens)}")
