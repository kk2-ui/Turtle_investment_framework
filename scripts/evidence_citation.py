#!/usr/bin/env python3
"""evidence_citation.py — V10：证据引用强制系统。

管理证据源注册、验证引用锚点、标准化引用格式。

从 Dayu 的 audit_evidence_rewriter.py 裁剪而来。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

# [source: X] 锚点的正则模式
_SOURCE_ANCHOR_PATTERN = re.compile(r"\[source:\s*([^\]]+)\]")

# 已知数据源文件列表
_KNOWN_SOURCES = {
    "compute_bundle.json": "Zone A 定量计算结果",
    "compute_bundle_precise.json": "Zone A 精算结果",
    "financial_trends.json": "财务趋势数据",
    "industry_context.json": "行业背景数据",
    "mda.json": "管理层讨论与分析提取",
    "segments.json": "分部报告提取",
    "risks.json": "风险因素提取",
    "governance.json": "公司治理提取",
    "audit.json": "审计相关提取",
    "moat_assessment.json": "护城河评估（Zone J）",
    "capex_classification.json": "Capex 分类（Zone J）",
    "earnings_quality.json": "收益质量评估（Zone J）",
    "data_discount.json": "数据质量折价（Zone J）",
    "analysis_contract.json": "分析合同",
    "annual_report_2024": "2024 年年报",
    "annual_report_2023": "2023 年年报",
    "annual_report_2022": "2022 年年报",
    "annual_report_2021": "2021 年年报",
    "annual_report_2020": "2020 年年报",
}


@dataclass
class EvidenceRegistry:
    """证据源注册表。

    追踪所有可用的证据来源及其引用情况。

    Args:
        sources: 已知来源名称 → 描述的映射。
        cited_sources: 已被引用的来源集合。
    """

    sources: dict[str, str] = field(default_factory=lambda: dict(_KNOWN_SOURCES))
    cited_sources: set[str] = field(default_factory=set)

    def register_source(self, name: str, description: str = "") -> None:
        """注册新的证据来源。

        Args:
            name: 来源名称（如文件名）。
            description: 来源描述。
        """
        self.sources[name] = description

    def register_from_output_dir(self, stock_dir: str) -> None:
        """从输出目录自动注册所有可用的 JSON 文件作为证据来源。

        Args:
            stock_dir: 股票输出目录路径。
        """
        for fname in os.listdir(stock_dir):
            if fname.endswith(".json"):
                name = fname
                desc = _KNOWN_SOURCES.get(name, f"数据文件: {name}")
                self.sources[name] = desc
            elif fname.endswith(".pdf"):
                self.sources[fname] = f"年报 PDF: {fname}"

    def validate_anchors(self, content: str) -> list[dict[str, str]]:
        """验证内容中的所有证据锚点。

        Args:
            content: 章节或报告内容。

        Returns:
            问题列表，每项包含 {anchor, issue}。
        """
        issues: list[dict[str, str]] = []
        anchors = _SOURCE_ANCHOR_PATTERN.findall(content)

        for anchor in anchors:
            anchor = anchor.strip()
            if not anchor:
                issues.append({"anchor": anchor, "issue": "空来源引用"})
                continue
            if anchor not in self.sources:
                # 检查模糊匹配
                matched = False
                for known in self.sources:
                    if anchor in known or known in anchor:
                        matched = True
                        break
                if not matched:
                    issues.append({"anchor": anchor, "issue": f"未知来源: {anchor}"})

        return issues

    def get_uncited_sources(self, content: str) -> list[str]:
        """获取存在但未被引用的数据源。

        Args:
            content: 报告内容。

        Returns:
            未被引用的来源名称列表。
        """
        cited = set(a.strip() for a in _SOURCE_ANCHOR_PATTERN.findall(content))
        # 只检查 Zone B/J 的关键输出文件
        key_sources = {
            "mda.json", "segments.json", "risks.json", "governance.json",
            "audit.json", "moat_assessment.json", "capex_classification.json",
            "earnings_quality.json", "data_discount.json",
        }
        return sorted(key_sources - cited)

    def extract_all_sources(self, content: str) -> list[str]:
        """提取内容中的所有去重来源引用。

        Args:
            content: 报告内容。

        Returns:
            排序后的去重来源列表。
        """
        anchors = _SOURCE_ANCHOR_PATTERN.findall(content)
        seen: set[str] = set()
        result: list[str] = []
        for a in anchors:
            a = a.strip()
            if a and a not in seen:
                seen.add(a)
                result.append(a)
        return sorted(result)

    def get_source_description(self, source_name: str) -> str:
        """获取来源的描述。

        Args:
            source_name: 来源名称。

        Returns:
            描述文本。
        """
        return self.sources.get(source_name, "未知来源")


def normalize_evidence_section(content: str) -> str:
    """标准化证据引用格式。

    将各种格式的证据引用统一为 [source: X] 格式。

    Args:
        content: 原始内容。

    Returns:
        标准化后的内容。
    """
    # 标准化常见变体
    replacements = [
        (r"\[来源:\s*([^\]]+)\]", r"[source: \1]"),
        (r"\[Source:\s*([^\]]+)\]", r"[source: \1]"),
        (r"\[src:\s*([^\]]+)\]", r"[source: \1]"),
        (r"\(见\s*([^)]+)\)", r"[source: \1]"),
    ]
    result = content
    for pat, repl in replacements:
        result = re.sub(pat, repl, result)
    return result


def validate_evidence_coverage(
    content: str,
    registry: EvidenceRegistry | None = None,
) -> dict[str, Any]:
    """检查内容的证据覆盖率。

    Args:
        content: 报告内容。
        registry: 证据注册表（可选）。

    Returns:
        覆盖率报告字典。
    """
    if registry is None:
        registry = EvidenceRegistry()

    # 统计数字声明
    number_pattern = re.compile(r"\d+[\.\d]*\s*(%|亿|万|M|B|HKD|RMB|元|倍|x|亿港元|亿元)")
    number_claims = len(number_pattern.findall(content))

    # 统计证据锚点
    evidence_anchors = len(_SOURCE_ANCHOR_PATTERN.findall(content))

    # 唯一来源数
    unique_sources = len(registry.extract_all_sources(content))

    # 覆盖率 = 锚点数 / max(数字声明, 1)
    coverage = evidence_anchors / max(number_claims, 1)

    # 未知来源
    unknown = [i for i in registry.validate_anchors(content) if "未知来源" in str(i.get("issue", ""))]

    # 未被引用的关键来源
    uncited = registry.get_uncited_sources(content)

    return {
        "number_claims": number_claims,
        "evidence_anchors": evidence_anchors,
        "unique_sources": unique_sources,
        "coverage_ratio": round(coverage, 2),
        "unknown_sources": len(unknown),
        "uncited_key_sources": uncited,
        "status": "PASS" if coverage >= 0.3 and not unknown else "WARN" if coverage >= 0.1 else "FAIL",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="证据引用验证与标准化")
    ap.add_argument("file", help="Markdown 文件路径")
    ap.add_argument("--stock-dir", help="股票输出目录（用于加载可用来源）")
    ap.add_argument("--normalize", action="store_true", help="标准化引用格式")
    args = ap.parse_args()

    with open(args.file, encoding="utf-8") as f:
        content = f.read()

    registry = EvidenceRegistry()
    if args.stock_dir:
        registry.register_from_output_dir(args.stock_dir)

    if args.normalize:
        normalized = normalize_evidence_section(content)
        out_path = args.file.replace(".md", "_normalized.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(normalized)
        print(f"✅ 已标准化 → {out_path}")
        sys.exit(0)

    # 验证
    coverage = validate_evidence_coverage(content, registry)
    print(f"证据覆盖率报告:")
    print(f"  数字声明: {coverage['number_claims']}")
    print(f"  证据锚点: {coverage['evidence_anchors']}")
    print(f"  唯一来源: {coverage['unique_sources']}")
    print(f"  覆盖率: {coverage['coverage_ratio']:.0%}")
    print(f"  未知来源: {coverage['unknown_sources']}")
    print(f"  未引用关键源: {coverage['uncited_key_sources']}")
    print(f"  状态: {coverage['status']}")

    # 详细检查
    issues = registry.validate_anchors(content)
    if issues:
        print(f"\n⚠️ 证据问题 ({len(issues)} 项):")
        for i in issues:
            print(f"  - [{i['anchor']}] {i['issue']}")
