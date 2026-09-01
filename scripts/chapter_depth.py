"""Minimal non-empty-shell contract for v13 report chapters.

Judgment quality is enforced by the claim, evidence, model and reader
contracts.  This module only rejects an empty body and keeps a small
traceability diagnostic for numeric claims.  It deliberately does not
reward length, number density, formula count, headings or available file
volume.
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

# The diagnostic highlights roughly one evidence anchor for every four numeric
# claim units a chapter chooses to make.  There is no fixed citation quota:
# a chapter with no numeric claim is judged by the claim/evidence contracts,
# not forced to manufacture numbers or citations here.
MIN_EVIDENCE_PER_NUMERIC_CLAIM = 0.25
MIN_SUBSTANTIVE_BODY_CHARS = 10


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
    """Return the minimal shell requirement, independent of data abundance.

    ``data_rich`` and ``quality_profile`` remain inputs because callers use
    them to describe the run.  They must not make the writing quota larger:
    more available files are an opportunity to improve a material judgment,
    not a reason to pad every chapter.
    """
    del chapter_index, data_rich, quality_profile
    return {
        "min_substantive_chars": MIN_SUBSTANTIVE_BODY_CHARS,
        "min_numeric_claim_lines": 0,
        "min_analysis_lines": 0,
        "min_derivation_lines": 0,
        "min_evidence_anchors": 0,
        "min_section_headings": 0,
    }


def semantic_depth_prompt(*, data_rich: bool = False) -> str:
    """Compact anti-padding contract shared with the generation prompt."""
    profile_note = (
        "本标的可用资料较多；只使用会改变本章判断的材料，不因文件更多扩大篇幅。"
        if data_rich else
        "本标的使用标准数据档；数据缺失必须明示，不得编造。"
    )
    return f"""## 章节非空壳契约

本契约只防止空章和模板壳，不评价研究深度。判断质量由 claim、证据、模型和读者合同负责。
{profile_note}

- 写出本章范围内的当前判断，并优先说明经济机制、最强反方、经营情景、翻转事实和投资含义；纯标题或明确占位符不能通过，模板话术不能代替判断。
- 不设字数、数字、公式、标题数量或基础引用配额。资料多不要求写得更长，资料少也不能用 `UNKNOWN` 取消仍可成立的公司判断。
- 金额、比例、倍数等材料主张继续服从已有 claim-evidence 合同；这里的计数只用于诊断，不改变完成状态。没有数字时不得为过门补数字或引用。
- 以三个最重要判断闭环为止。禁止重复结论、拆句、堆阈值、堆引用或增加小节来通过检查。
- write_chapter 若返回非空壳失败，只补一个缺失的实质判断或原因，不扩写无关内容。
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
        "evidence_claim_lines": sum(bool(_EVIDENCE_CLAIM_RE.search(unit)) for unit in units),
        "analysis_lines": sum(bool(_ANALYSIS_RE.search(unit)) for unit in units),
        "derivation_lines": sum(bool(_DERIVATION_RE.search(unit)) for unit in units),
        "evidence_anchors": len(_SOURCE_RE.findall(content)),
        "section_headings": len(re.findall(r"^#{2,6}\s+", content, re.MULTILINE)),
        "nonempty_lines": sum(bool(line.strip()) for line in content.splitlines()),
    }
    recommended_evidence_anchors = math.ceil(
        metrics["evidence_claim_lines"] * MIN_EVIDENCE_PER_NUMERIC_CLAIM
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
        "diagnostics": {
            "recommended_evidence_anchors_for_numeric_claims": recommended_evidence_anchors,
            "numeric_evidence_anchor_shortfall": max(
                0, recommended_evidence_anchors - metrics["evidence_anchors"]
            ),
        },
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
