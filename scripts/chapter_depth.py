"""Semantic chapter-depth contract for v13 reports.

The old contract counted non-empty Markdown lines.  That encouraged models to
put every sentence on its own line and made paragraph cleanup look like a loss
of depth.  This module measures content that survives formatting changes.
"""

from __future__ import annotations

import re
import math
import json
import os
from typing import Any


QUANTITATIVE_CHAPTER_INDEXES = {10, 11, 12, 13, 14}

# Kept as compatibility metadata for older callers and reports.  They are no
# longer used as pass/fail gates.
MIN_QUALITATIVE_LINES = 80
MIN_QUANTITATIVE_LINES = 120

_SOURCE_RE = re.compile(r"\[source:\s*[^\]]+\]", re.IGNORECASE)
_NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+−]?\d+(?:[,.]\d+)*(?:\s*(?:%|pp|pct|亿|万|M|B|HKD|RMB|元|倍|x))?", re.IGNORECASE)
_EVIDENCE_CLAIM_RE = re.compile(
    r"\d+[\.\d]*\s*(?:%|亿|万|M|B|HKD|RMB|元|倍|x|亿港元|亿元)",
    re.IGNORECASE,
)
_ANALYSIS_RE = re.compile(
    r"因此|所以|说明|意味着|驱动|因为|如果|但|然而|风险|判断|核心|验证|"
    r"导致|反映|可见|相比|相较|取决于|结论|假设|敏感|情景|约束|矛盾"
)
_DERIVATION_RE = re.compile(
    r"[=＝≈]|→|−|\+|公式|推导|拆解|调整后|归一化|基准|悲观|乐观|"
    r"敏感|情景|假设|口径|折现|安全边际|相比|相较|因此|所以"
)

# A chapter should cite roughly one evidence anchor for every four numeric
# claim units.  Fixed floors alone let dense quantitative/risk chapters pass
# with only three citations, which made reports formally complete but less
# traceable after context compaction.
MIN_EVIDENCE_PER_NUMERIC_CLAIM = 0.25
_EVIDENCE_ANCHOR_FLOORS = {
    0: 8,
    4: 12,
    8: 12,
    9: 12,
    11: 18,
    12: 18,
    13: 20,
    14: 15,
}

# Source-deepening raises traceability where it matters, but deliberately does
# not impose prose length or analysis-unit quotas.  The V3 structured gates
# judge claim support, competing explanations and model validity directly.
SOURCE_DEEPENING_FLOORS: dict[int, dict[str, int]] = {
    8: {"min_evidence_anchors": 20},
    9: {"min_evidence_anchors": 16},
    11: {"min_evidence_anchors": 20},
    12: {"min_evidence_anchors": 20},
    13: {"min_evidence_anchors": 22},
    14: {"min_evidence_anchors": 18},
}


def detect_data_richness(output_dir: str) -> bool:
    """Return whether the output has enough primary/structured data for a deep report."""
    if not os.path.isdir(output_dir):
        return False
    zone_files = ("mda.json", "segments.json", "risks.json", "governance.json", "audit.json")
    available_zones = 0
    for name in zone_files:
        path = os.path.join(output_dir, name)
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        if data and not (isinstance(data, dict) and data.get("_missing")):
            available_zones += 1
    annual_markdown = sum(
        bool(re.fullmatch(r"20\d{2}_年报\.md", name))
        for name in os.listdir(output_dir)
    )
    return available_zones >= 4 and annual_markdown >= 4


def depth_requirements(
    chapter_index: int,
    *,
    data_rich: bool = False,
    quality_profile: str = "standard",
) -> dict[str, int]:
    """Return the single canonical depth requirement for a chapter identity."""
    if chapter_index in QUANTITATIVE_CHAPTER_INDEXES:
        requirements = {
            "min_substantive_chars": 1600 if data_rich else 1000,
            "min_numeric_claim_lines": 12 if data_rich else 8,
            "min_analysis_lines": 10 if data_rich else 6,
            "min_derivation_lines": 10 if data_rich else 6,
            "min_evidence_anchors": _EVIDENCE_ANCHOR_FLOORS.get(chapter_index, 10),
            "min_section_headings": 4 if data_rich else 3,
        }
    else:
        requirements = {
            "min_substantive_chars": 1200 if data_rich else 800,
            "min_numeric_claim_lines": 8 if data_rich else 4,
            "min_analysis_lines": 8 if data_rich else 4,
            "min_derivation_lines": 0,
            "min_evidence_anchors": _EVIDENCE_ANCHOR_FLOORS.get(chapter_index, 6),
            "min_section_headings": 4 if data_rich else 3,
        }
    if quality_profile == "source_deepening" and data_rich:
        for key, value in SOURCE_DEEPENING_FLOORS.get(chapter_index, {}).items():
            requirements[key] = max(requirements.get(key, 0), value)
    return requirements


def semantic_depth_prompt(*, data_rich: bool = False) -> str:
    """Compact generation contract shared with the DeepSeek system prompt."""
    qualitative = depth_requirements(1, data_rich=data_rich)
    quantitative = depth_requirements(10, data_rich=data_rich)
    profile_note = (
        "本标的数据丰富（至少4类Zone B且4年以上年报），启用高信息密度档；"
        "不得贴着最低门槛写短章。"
        if data_rich else
        "本标的使用标准数据档；数据缺失必须明示，不得编造。"
    )
    target_note = "字符数只设防空壳下限，不设目标区间；以关键问题闭环为止，禁止为过门重复结论、拆句或堆阈值。"
    return f"""## 章节语义深度契约（首稿即满足）

深度按语义内容计算，与 Markdown 行数无关；禁止逐句换行、重复结论或堆模板话术凑长度。
{profile_note}

- Ch0-Ch9 定性章：实质正文≥{qualitative['min_substantive_chars']}字符；数字声明≥{qualitative['min_numeric_claim_lines']}条；分析/因果判断≥{qualitative['min_analysis_lines']}条；基础证据锚点≥{qualitative['min_evidence_anchors']}个；H2-H4 小节标题≥{qualitative['min_section_headings']}个。
- Ch10-Ch14 定量章：实质正文≥{quantitative['min_substantive_chars']}字符；数字声明≥{quantitative['min_numeric_claim_lines']}条；分析/因果判断≥{quantitative['min_analysis_lines']}条；公式/情景/推导≥{quantitative['min_derivation_lines']}条；基础证据锚点≥{quantitative['min_evidence_anchors']}个；H2-H4 小节标题≥{quantitative['min_section_headings']}个。
- 证据锚点最终要求动态取 `max(章节基础值, ceil(含单位数字声明行×{MIN_EVIDENCE_PER_NUMERIC_CLAIM:.0%}))`，即约每4行金额/比例/倍数声明至少1个真实来源。普通年份、章节编号和同一行内的来源注释不抬高分母，避免补引用时门槛追涨。Ch4/Ch9 风险变化章和 Ch11-Ch14 裁决章有更高基础值；来源可在段末合并，但不得因同一文件已引用过而省略新数字的来源。
- {target_note} 数据不足时明确缺口，绝不编造。
- write_chapter 返回 `depth.metrics/failures`。若首稿未通过，只补失败维度及必要上下文，不要整章推倒重写；第二次仍未通过就转下一章，交给 fresh-context repair。
"""


def _meaningful_lines(content: str) -> list[str]:
    lines: list[str] = []
    for raw in content.splitlines():
        text = raw.strip()
        if not text or text.startswith("#") or text.startswith("---"):
            continue
        if text.startswith("[source:") or re.fullmatch(r"\|?[\s:|-]+\|?", text):
            continue
        text = _SOURCE_RE.sub("", text)
        text = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s*)", "", text)
        text = re.sub(r"[`*_~]", "", text)
        text = re.sub(r"\|", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            lines.append(text)
    return lines


def analyze_chapter_depth(
    content: str,
    chapter_index: int,
    *,
    data_rich: bool = False,
    quality_profile: str = "standard",
) -> dict[str, Any]:
    """Measure semantic depth and return metrics plus explicit failures."""
    meaningful = _meaningful_lines(content)
    semantic_text = " ".join(meaningful)
    units = [
        unit.strip()
        for line in meaningful
        for unit in re.split(r"(?<=[。！？!?；;])\s*", line)
        if unit.strip()
    ]
    requirements = depth_requirements(
        chapter_index,
        data_rich=data_rich,
        quality_profile=quality_profile,
    )
    metrics = {
        "substantive_chars": len(re.sub(r"\s+", "", semantic_text)),
        # Historical JSON field names retain ``_lines`` for compatibility, but
        # the counting unit is now a semantic sentence/table row, not a newline.
        "numeric_claim_lines": sum(bool(_NUMBER_RE.search(unit)) for unit in units),
        "evidence_claim_lines": sum(
            bool(_EVIDENCE_CLAIM_RE.search(line)) for line in content.splitlines()
        ),
        "analysis_lines": sum(bool(_ANALYSIS_RE.search(unit)) for unit in units),
        "derivation_lines": sum(bool(_DERIVATION_RE.search(unit)) for unit in units),
        "evidence_anchors": len(_SOURCE_RE.findall(content)),
        "section_headings": len(re.findall(r"^#{2,6}\s+", content, re.MULTILINE)),
        "nonempty_lines": sum(bool(line.strip()) for line in content.splitlines()),
    }
    requirements["min_evidence_anchors"] = max(
        requirements["min_evidence_anchors"],
        math.ceil(metrics["evidence_claim_lines"] * MIN_EVIDENCE_PER_NUMERIC_CLAIM),
    )
    mapping = {
        "substantive_chars": "min_substantive_chars",
        "numeric_claim_lines": "min_numeric_claim_lines",
        "analysis_lines": "min_analysis_lines",
        "derivation_lines": "min_derivation_lines",
        "evidence_anchors": "min_evidence_anchors",
        "section_headings": "min_section_headings",
    }
    failures = [
        f"{metric}:{metrics[metric]}<{requirements[requirement]}"
        for metric, requirement in mapping.items()
        if metrics[metric] < requirements[requirement]
    ]
    return {
        "status": "PASS" if not failures else "FAIL",
        "chapter_index": chapter_index,
        "profile": (
            ((quality_profile + "_") if quality_profile != "standard" else "")
            + ("rich_" if data_rich else "")
            + ("quantitative" if chapter_index in QUANTITATIVE_CHAPTER_INDEXES else "qualitative")
        ),
        "metrics": metrics,
        "requirements": requirements,
        "failures": failures,
    }


def depth_failure_description(result: dict[str, Any]) -> str:
    """Human-readable repair feedback without line-count incentives."""
    labels = {
        "substantive_chars": "实质正文字符",
        "numeric_claim_lines": "含数字声明",
        "analysis_lines": "分析/因果判断",
        "derivation_lines": "公式/情景/推导",
        "evidence_anchors": "证据锚点",
        "section_headings": "小节标题",
    }
    parts: list[str] = []
    for failure in result.get("failures", []):
        metric, comparison = failure.split(":", 1)
        parts.append(f"{labels.get(metric, metric)} {comparison}")
    return "；".join(parts)
