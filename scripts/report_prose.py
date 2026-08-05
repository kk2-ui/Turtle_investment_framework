"""Conservative Markdown prose normalization and narrative-efficiency metrics."""

from __future__ import annotations

import re
from typing import Any


_STRUCTURAL_RE = re.compile(
    r"^(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|\||>|---|```|\[\^?\d+\]:|\[source:|"
    r"\*\*[^*]+\*\*[：:])"
)
_FORMULA_RE = re.compile(r"(?:^|\s)[A-Za-z][A-Za-z0-9_*]{0,15}\s*[=＝]|\$\$|\\begin\{")


def _blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def _is_prose(block: str) -> bool:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    return bool(lines) and not any(_STRUCTURAL_RE.match(line) for line in lines)


def _sentence_count(block: str) -> int:
    return max(1, len(re.findall(r"[。！？!?；;]", block)))


def normalize_markdown_paragraphs(
    text: str,
    *,
    max_chars: int = 600,
    max_blocks: int = 3,
) -> str:
    """Merge only adjacent short one-sentence prose blocks.

    Headings, lists, tables, quotes, formulas, warnings and footnotes are hard
    boundaries.  The cap prevents a mechanical wall of text.
    """
    blocks = _blocks(text)
    output: list[str] = []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        if not _is_prose(block) or _FORMULA_RE.search(block) or _sentence_count(block) > 1:
            output.append(block)
            i += 1
            continue
        merged = [block]
        size = len(block)
        j = i + 1
        while j < len(blocks) and len(merged) < max_blocks:
            candidate = blocks[j]
            if not _is_prose(candidate) or _FORMULA_RE.search(candidate) or _sentence_count(candidate) > 1:
                break
            if size + len(candidate) + 1 > max_chars:
                break
            merged.append(candidate)
            size += len(candidate) + 1
            j += 1
        output.append(" ".join(part.replace("\n", " ") for part in merged))
        i = j
    return "\n\n".join(output) + ("\n" if text.endswith("\n") else "")


def narrative_efficiency_metrics(text: str) -> dict[str, Any]:
    """Measure fragmentation and repetition without penalizing Markdown spacing."""
    prose = [block for block in _blocks(text) if _is_prose(block)]
    eligible = [block for block in prose if len(block) <= 240 and not _FORMULA_RE.search(block)]
    single = [block for block in eligible if _sentence_count(block) <= 1]
    normalized = [
        re.sub(r"\d+(?:[,.]\d+)*", "N", re.sub(r"\s+", "", block)).lower()
        for block in prose
    ]
    duplicate_count = len(normalized) - len(set(normalized))
    single_ratio = len(single) / max(len(eligible), 1)
    duplicate_ratio = duplicate_count / max(len(normalized), 1)
    issues: list[str] = []
    if len(eligible) >= 20 and single_ratio > 0.65:
        issues.append(f"单句碎片段落过多: {len(single)}/{len(eligible)} ({single_ratio:.1%})")
    if len(normalized) >= 20 and duplicate_ratio > 0.08:
        issues.append(f"重复段落过多: {duplicate_count}/{len(normalized)} ({duplicate_ratio:.1%})")
    return {
        "prose_paragraphs": len(prose),
        "eligible_short_paragraphs": len(eligible),
        "single_sentence_paragraphs": len(single),
        "single_sentence_ratio": single_ratio,
        "duplicate_paragraphs": duplicate_count,
        "duplicate_ratio": duplicate_ratio,
        "issues": issues,
    }
