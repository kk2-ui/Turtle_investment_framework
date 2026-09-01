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
from pathlib import Path
from typing import Any

# [source: X] 锚点的正则模式
_SOURCE_ANCHOR_PATTERN = re.compile(r"\[source:\s*([^\]]+)\]")
_TABLE_SOURCE_ANCHOR_PATTERN = re.compile(r"\[table-source:\s*([^\]]+)\]", re.IGNORECASE)


def extract_evidence_anchors(content: str) -> list[str]:
    """Extract ordinary and table-level source anchors in document order."""
    matches = [
        (match.start(), match.group(1))
        for pattern in (_SOURCE_ANCHOR_PATTERN, _TABLE_SOURCE_ANCHOR_PATTERN)
        for match in pattern.finditer(content)
    ]
    return [value for _, value in sorted(matches)]

MIN_EVIDENCE_COVERAGE_RATIO = 0.45

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

_PSEUDO_SOURCES = {
    "report_internal": "报告内部交叉引用（Ch0–Ch14）",
    "framework_method": "Turtle 框架方法论与关卡定义",
    "report_derivation": "基于已引证输入的报告内公式推导",
    "public_market_research": "行业公开资料与外部市场研究（原始链接待结构化）",
    "financial_statement_db": "stock_analysis.db 财务报表明细",
    "unresolved_evidence": "未解析证据身份（发布前必须修复）",
}

_TOOL_SOURCE_ALIASES = {
    "compute_aa": "compute_bundle.json",
    "compute_gg": "compute_bundle.json",
    "compute_ddm": "compute_bundle.json",
    "compute_bundle_db": "compute_bundle.json",
    "compute_data_quality": "compute_bundle.json",
    "get_financial_trends": "financial_trends.json",
    "get_financial_statement": "financial_statement_db",
    "get_peer_comparison": "industry_context.json",
    "get_global_benchmarks": "industry_context.json",
    "peer_comparison": "industry_context.json",
    "industry_context": "industry_context.json",
    "get_market_data": "compute_bundle.json",
    "market_data": "compute_bundle.json",
    "company_context_memory": "company_context_memory.json",
    "moat_assessment": "moat_assessment.json",
    "mda": "mda.json",
    "segments": "segments.json",
    "risks": "risks.json",
    "governance": "governance.json",
    "audit": "audit.json",
    "financial_trends": "financial_trends.json",
    "decision_manifest": "decision_manifest.json",
}


@dataclass
class EvidenceRegistry:
    """证据源注册表。

    追踪所有可用的证据来源及其引用情况。

    Args:
        sources: 已知来源名称 → 描述的映射。
        cited_sources: 已被引用的来源集合。
    """

    sources: dict[str, str] = field(default_factory=lambda: {**_KNOWN_SOURCES, **_PSEUDO_SOURCES})
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
            elif re.match(r"20\d{2}_年报\.md$", fname):
                self.sources[fname] = f"年报 Markdown: {fname}"
        manifest_path = os.path.join(stock_dir, "document_manifest.json")
        try:
            with open(manifest_path, encoding="utf-8") as handle:
                manifest = json.load(handle)
        except (OSError, json.JSONDecodeError):
            manifest = {}
        for document in manifest.get("documents") or []:
            if not isinstance(document, dict) or not document.get("doc_id"):
                continue
            doc_id = str(document["doc_id"])
            self.sources[doc_id] = (
                f"官方证据: {document.get('doc_type')} {document.get('period_end')} "
                f"{document.get('local_path')}"
            )
        # Structured writers use immutable evidence identities rather than
        # filenames.  Register only identities that actually exist in the
        # current output; otherwise a syntactically plausible OBS/CALC/EVD id
        # would be blessed without evidence.
        structured_sources = (
            ("fact_observations.json", "observations", "observation_id", "status"),
            ("calculation_observations.json", "calculations", "calculation_id", "status"),
        )
        for filename, collection, id_field, status_field in structured_sources:
            try:
                payload = json.loads(
                    Path(stock_dir, filename).read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                payload = {}
            for item in payload.get(collection) or []:
                if not isinstance(item, dict) or not item.get(id_field):
                    continue
                status = str(item.get(status_field) or "VERIFIED").upper()
                if status not in {"VERIFIED", "PASS", "VALID"}:
                    continue
                identity = str(item[id_field])
                self.sources[identity] = f"结构化证据: {filename}"
        try:
            claim_payload = json.loads(
                Path(stock_dir, "claim_evidence.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            claim_payload = {}
        for claim in claim_payload.get("claims") or []:
            if not isinstance(claim, dict):
                continue
            for item in claim.get("raw_facts") or []:
                if isinstance(item, dict) and item.get("evidence_id"):
                    identity = str(item["evidence_id"])
                    self.sources[identity] = "结构化证据: claim_evidence.json"

    def canonicalize_anchor(self, anchor: str) -> tuple[list[str], list[str]]:
        """Resolve a descriptive/compound anchor into canonical evidence sources."""
        text = str(anchor or "").strip()
        canonical: list[str] = []
        unresolved: list[str] = []

        def add(name: str) -> None:
            if name and name not in canonical:
                canonical.append(name)

        parts = [part.strip() for part in re.split(r"\s+\+\s+|[；;]", text) if part.strip()]
        inherited_sources: list[str] = []
        for part in parts or [text]:
            matched = False
            # Exact filenames may carry a field/page suffix; retain the file identity.
            for known in self.sources:
                if known in _PSEUDO_SOURCES:
                    continue
                if known.lower() in part.lower():
                    add(known)
                    matched = True
            for alias, source in _TOOL_SOURCE_ALIASES.items():
                if alias == "mda" and re.search(r"20\d{2}[\s_]*年?年报", part, re.IGNORECASE):
                    # ``MDA`` here is a section locator inside the annual
                    # report, not a citation of the derived mda.json file.
                    continue
                if re.search(rf"(?<![A-Za-z0-9_]){re.escape(alias)}(?![A-Za-z0-9_])", part, re.IGNORECASE):
                    add(source)
                    matched = True
            # Writers commonly cite the PDF identity returned by the reader
            # (``2025_年报.pdf``) while isolated acceptance seeds retain the
            # page-marked Markdown twin. Resolve both to the same fiscal-year
            # evidence identity instead of treating the extension as a source
            # conflict.
            annual = re.search(r"(20\d{2})[\s_]*年?年报", part)
            if annual:
                year_source = f"{annual.group(1)}_年报.md"
                add(year_source if year_source in self.sources else f"annual_report_{annual.group(1)}")
                matched = True
            searched_annual = re.search(r"search_report\s+FY(20\d{2})", part, re.IGNORECASE)
            if searched_annual:
                year_source = f"{searched_annual.group(1)}_年报.md"
                add(year_source if year_source in self.sources else f"annual_report_{searched_annual.group(1)}")
                matched = True
            elif re.search(r"\bsearch_report\b", part, re.IGNORECASE):
                annual_sources = sorted(name for name in self.sources if re.match(r"20\d{2}_年报\.md$", name))
                if annual_sources:
                    add(annual_sources[-1])
                    matched = True
            if re.search(r"(?<![A-Za-z0-9_])Ch(?:apter)?\s*\d+(?!\d)", part, re.IGNORECASE):
                add("report_internal")
                matched = True
            if re.search(r"framework|关卡|routing|框架|r5_return|asset_value|cost_of_capital", part, re.IGNORECASE):
                add("framework_method")
                matched = True
            if re.search(r"自行(?:推导|计算|判断)|自算|本计算|综合判断|敏感性推导|公式推导|行业判断|(?:^|\b)derivation(?:\b|$)|P[^；;\n]{0,12}推导", part, re.IGNORECASE):
                add("report_derivation")
                matched = True
            if re.search(r"阈值基于|历史波动和行业对比", part):
                add("framework_method")
                matched = True
            if re.search(r"本分析|综合分析|以上各来源|投资者操作指引|推算|基于GG公式推导", part, re.IGNORECASE):
                add("report_derivation")
                matched = True
            if re.search(r"^计算\b|计算\s*P(?:\\+)?\*", part, re.IGNORECASE):
                add("report_derivation")
                matched = True
            if re.search(r"\binvestor preference\b", part, re.IGNORECASE):
                add("framework_method")
                matched = True
            if re.search(r"全链路|参数假设|系统提示|冲突裁决|逆运算|手动计算|合成矩阵|DDM公式", part, re.IGNORECASE):
                add("report_derivation")
                matched = True
            if re.search(r"^DPS\s*[\d.]", part, re.IGNORECASE):
                add("report_derivation")
                matched = True
            if re.search(r"行业公开数据|web_search|web_fetch|国际对标数据", part, re.IGNORECASE):
                add("public_market_research")
                matched = True
            if re.search(
                r"新浪财经|奥维云网|雪球|第一财经|东方财富|搜狐|21世纪经济报道|高盛",
                part,
                re.IGNORECASE,
            ):
                add("public_market_research")
                matched = True
            if re.search(
                r"(?<![A-Za-z0-9-])(?:https?://)?(?:[A-Za-z0-9-]+\.)+"
                r"(?:com|cn|org|net|gov|edu)(?:\.cn)?(?:/|\b)",
                part,
                re.IGNORECASE,
            ):
                add("public_market_research")
                matched = True
            if re.search(r"公司年报|年报(?:STMT|未披露)|代表性项目|章程修订|FY20\d{2}\s*协议", part, re.IGNORECASE):
                annual_sources = sorted(name for name in self.sources if re.match(r"20\d{2}_年报\.md$", name))
                if annual_sources:
                    add(annual_sources[-1])
                    matched = True
            if re.search(r"\b(?:shares|fx)\s*=|compute_bundle\b", part, re.IGNORECASE):
                add("compute_bundle.json")
                matched = True
            if re.search(r"\b(?:balance_sheet|income_statement|cash_flow)\b", part, re.IGNORECASE):
                add("financial_statement_db")
                matched = True
            if re.search(r"\bposition\b.*\bcapped_pct\b", part, re.IGNORECASE):
                add("compute_bundle.json")
                matched = True
            if (
                not matched
                and inherited_sources
                and re.search(
                    r"(?:[A-Za-z_][A-Za-z0-9_.]*\s*=)"
                    r"|(?:[\u4e00-\u9fffA-Za-z_/]+\s*[+\-−]?\d[\d,.]*)",
                    part,
                )
                and not re.search(r"https?://|\b(?:blog|forum|rumou?r|传闻)\b", part, re.IGNORECASE)
            ):
                # A compound anchor commonly states one source identity once,
                # followed by several semicolon-separated fields from the same
                # table/tool.  Preserve that identity without blessing a second
                # URL or prose-only source.
                for source in inherited_sources:
                    add(source)
                matched = True
            if not matched:
                unresolved.append(part)
            elif canonical:
                inherited_sources = list(canonical)
        return canonical, unresolved

    def extract_canonical_sources(self, content: str) -> list[str]:
        """Return de-duplicated canonical source identities used by the report."""
        seen: set[str] = set()
        result: list[str] = []
        for anchor in extract_evidence_anchors(content):
            canonical, unresolved = self.canonicalize_anchor(anchor)
            for source in canonical:
                if source not in seen:
                    seen.add(source)
                    result.append(source)
            if unresolved and "unresolved_evidence" not in seen:
                seen.add("unresolved_evidence")
                result.append("unresolved_evidence")
        return sorted(result)

    def validate_anchors(self, content: str) -> list[dict[str, str]]:
        """验证内容中的所有证据锚点。

        Args:
            content: 章节或报告内容。

        Returns:
            问题列表，每项包含 {anchor, issue}。
        """
        issues: list[dict[str, str]] = []
        anchors = extract_evidence_anchors(content)

        for anchor in anchors:
            anchor = anchor.strip()
            if not anchor:
                issues.append({"anchor": anchor, "issue": "空来源引用"})
                continue
            _, unresolved = self.canonicalize_anchor(anchor)
            if unresolved:
                issues.append({
                    "anchor": anchor,
                    "issue": "未知来源组件: " + " | ".join(unresolved),
                })

        return issues

    def get_uncited_sources(self, content: str) -> list[str]:
        """获取存在但未被引用的数据源。

        Args:
            content: 报告内容。

        Returns:
            未被引用的来源名称列表。
        """
        cited = set(self.extract_canonical_sources(content))
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
        anchors = extract_evidence_anchors(content)
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

    # A claim is a line/row containing one or more numeric facts. Counting each
    # numeric token made dense tables look artificially uncited.
    number_pattern = re.compile(r"\d+[\.\d]*\s*(%|亿|万|M|B|HKD|RMB|元|倍|x|亿港元|亿元)")
    number_tokens = len(number_pattern.findall(content))
    number_claims = sum(1 for line in content.splitlines() if number_pattern.search(line))

    # 统计证据锚点
    evidence_anchors = len(extract_evidence_anchors(content))

    # 唯一来源数
    unique_sources = len(registry.extract_canonical_sources(content))

    # 没有数字断言时，本维度不适用；不能凭空奖励 100%。
    coverage = evidence_anchors / number_claims if number_claims else None

    # 未知来源
    unknown = [i for i in registry.validate_anchors(content) if "未知来源" in str(i.get("issue", ""))]

    # 未被引用的关键来源
    uncited = registry.get_uncited_sources(content)

    return {
        "number_claims": number_claims,
        "number_tokens": number_tokens,
        "evidence_anchors": evidence_anchors,
        "unique_sources": unique_sources,
        "coverage_ratio": round(coverage, 2) if coverage is not None else None,
        "unknown_sources": len(unknown),
        "uncited_key_sources": uncited,
        "status": (
            "FAIL" if unknown else
            "N/A" if coverage is None else
            "PASS" if coverage >= MIN_EVIDENCE_COVERAGE_RATIO else
            "WARN"
        ),
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
    ratio = coverage['coverage_ratio']
    print(f"  覆盖率: {ratio:.0%}" if ratio is not None else "  覆盖率: N/A")
    print(f"  未知来源: {coverage['unknown_sources']}")
    print(f"  未引用关键源: {coverage['uncited_key_sources']}")
    print(f"  状态: {coverage['status']}")

    # 详细检查
    issues = registry.validate_anchors(content)
    if issues:
        print(f"\n⚠️ 证据问题 ({len(issues)} 项):")
        for i in issues:
            print(f"  - [{i['anchor']}] {i['issue']}")
