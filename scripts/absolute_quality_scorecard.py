#!/usr/bin/env python3
"""Reference-independent research-execution audit and closure diagnostics.

This module deliberately does not produce a compensating score or letter grade.
Investment validity belongs to the structured V3 gates; chapter diagnostics are
review priorities and must not reward keyword, formula, threshold or prose volume.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from scripts.evidence_citation import EvidenceRegistry, extract_evidence_anchors
    from scripts.research_plan import CHAPTER_RESEARCH_SPECS
except ModuleNotFoundError:
    from evidence_citation import EvidenceRegistry, extract_evidence_anchors
    from research_plan import CHAPTER_RESEARCH_SPECS


_SOURCE_RE = re.compile(r"\[source:\s*([^\]]+)\]", re.IGNORECASE)
_ANY_SOURCE_RE = re.compile(r"\[(?:table-)?source:\s*([^\]]+)\]", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|pp|倍|x|元|亿|万)?", re.IGNORECASE)
_UNIT_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|pp|倍|x|元|亿|万|HKD|RMB)", re.IGNORECASE)
_FILLER_RE = re.compile(r"众所周知|显而易见|不难发现|毋庸置疑|值得注意的是|总的来说")

CRITICAL_CHAPTERS = {0, 9, 12, 13, 14}


def _chapter_path(output_dir: Path, idx: int) -> Path:
    path = output_dir / "chapters" / f"_ch{idx:02d}.md"
    return path if path.exists() else output_dir / f"_ch{idx:02d}.md"


def _duplicate_ratio(text: str) -> float:
    paragraphs = []
    for raw in re.split(r"\n\s*\n", text):
        normalized = re.sub(r"\[source:[^\]]+\]", "", raw)
        normalized = re.sub(r"\s+|[`*_#>|-]", "", normalized)
        if len(normalized) >= 40:
            paragraphs.append(normalized)
    return 0.0 if not paragraphs else (len(paragraphs) - len(set(paragraphs))) / len(paragraphs)


def _load_research_execution(output_dir: str) -> dict[str, Any]:
    path = Path(output_dir) / "research_execution.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "UNKNOWN", "chapters": {}}
    return payload if isinstance(payload, dict) else {"status": "UNKNOWN", "chapters": {}}


def _answered_topics(text: str, chapter_index: int) -> dict[str, bool]:
    """Require substance around a topic, not a lone keyword occurrence."""
    paragraphs = [item for item in re.split(r"\n\s*\n", text) if item.strip()]
    result: dict[str, bool] = {}
    for topic in CHAPTER_RESEARCH_SPECS[chapter_index]["topics"]:
        answered = False
        for paragraph in paragraphs:
            distinct_hits = sum(keyword.lower() in paragraph.lower() for keyword in topic["keywords"])
            source_supported = bool(_SOURCE_RE.search(paragraph) and len(paragraph) >= 60)
            quantified_explanation = bool(len(paragraph) >= 60 and _UNIT_NUMBER_RE.search(paragraph))
            has_substance = source_supported or quantified_explanation
            if distinct_hits >= 1 and has_substance:
                answered = True
                break
        result[topic["id"]] = answered
    return result


def _table_has_source(lines: list[str], idx: int) -> bool:
    if not lines[idx].lstrip().startswith("|"):
        return False
    start = idx
    end = idx
    while start > 0 and lines[start - 1].lstrip().startswith("|"):
        start -= 1
    while end + 1 < len(lines) and lines[end + 1].lstrip().startswith("|"):
        end += 1
    window = "\n".join(lines[max(0, start - 1):min(len(lines), end + 2)])
    return bool(re.search(r"\[table-source:\s*[^\]]+\]", window, re.IGNORECASE))


def _claim_evidence_adjacency(text: str) -> tuple[float | None, int, int]:
    lines = text.splitlines()
    claim_indexes = [
        idx for idx, line in enumerate(lines)
        if _UNIT_NUMBER_RE.search(line)
        and not line.lstrip().startswith("#")
        and not _ANY_SOURCE_RE.search(line)
    ]
    supported = 0
    for idx in claim_indexes:
        window = "\n".join(lines[max(0, idx - 1): min(len(lines), idx + 2)])
        if _ANY_SOURCE_RE.search(window) or _table_has_source(lines, idx):
            supported += 1
    # Lines with an inline source are claims too and are always adjacent.
    inline = sum(bool(_UNIT_NUMBER_RE.search(line) and _ANY_SOURCE_RE.search(line)) for line in lines)
    total = len(claim_indexes) + inline
    return ((supported + inline) / total if total else None), total, supported + inline


def _source_quality(text: str, registry: EvidenceRegistry) -> tuple[float, int, int]:
    anchors = extract_evidence_anchors(text)
    if not anchors:
        return 0.0, 0, 0
    evidence_identities = {
        "compute_bundle.json", "financial_statement_db", "financial_trends.json",
        "industry_context.json", "mda.json", "segments.json", "risks.json",
        "governance.json", "audit.json", "moat_assessment.json",
        "public_market_research",
    }
    valid = 0
    unresolved_count = 0
    for anchor in anchors:
        canonical, unresolved = registry.canonicalize_anchor(anchor)
        unresolved_count += len(unresolved)
        if any(item in evidence_identities or re.match(r"20\d{2}_年报\.md", item) for item in canonical):
            valid += 1
    return valid / len(anchors), len(anchors), unresolved_count


def score_chapter(
    text: str,
    chapter_index: int,
    output_dir: str,
    registry: EvidenceRegistry,
    research_execution: dict[str, Any],
) -> dict[str, Any]:
    topics = _answered_topics(text, chapter_index)
    question_ratio = sum(topics.values()) / len(topics) if topics else 1.0
    adjacency, numeric_claims, adjacent_claims = _claim_evidence_adjacency(text)
    source_quality, anchor_count, unresolved_count = _source_quality(text, registry)
    execution_entry = (research_execution.get("chapters") or {}).get(str(chapter_index))
    execution_status = "UNKNOWN"
    missing_executed_sections: list[str] = []
    if isinstance(execution_entry, dict):
        execution_status = "ENFORCED" if execution_entry.get("enforced") else "RECORDED"
        missing_executed_sections = list(execution_entry.get("missing_sections") or [])
    elif research_execution.get("enforced") and chapter_index in set(research_execution.get("expected_chapters") or []):
        execution_status = "ENFORCED_MISSING"
    duplicate_ratio = _duplicate_ratio(text)
    filler_count = len(_FILLER_RE.findall(text))
    hard_failures = []
    if unresolved_count:
        hard_failures.append(f"unknown_source_components:{unresolved_count}")
    if execution_status == "ENFORCED" and missing_executed_sections:
        hard_failures.append("required_source_reads_missing:" + ",".join(missing_executed_sections))
    if execution_status == "ENFORCED" and isinstance(execution_entry, dict):
        fiscal_years = set(execution_entry.get("fiscal_years") or [])
        tool_counts = execution_entry.get("tool_counts") or {}
        required_tools = set(CHAPTER_RESEARCH_SPECS[chapter_index].get("tools") or [])
        if len(fiscal_years) < 2:
            hard_failures.append(f"required_fiscal_year_reads_missing:{len(fiscal_years)}/2")
        if "search_report" in required_tools and int(tool_counts.get("search_report") or 0) < 3:
            hard_failures.append(f"required_search_report_missing:{int(tool_counts.get('search_report') or 0)}/3")
        if {"web_search", "web_fetch"}.intersection(required_tools):
            web_search_count = int(tool_counts.get("web_search") or 0)
            web_fetch_count = int(tool_counts.get("web_fetch") or 0)
            if web_search_count < 2:
                hard_failures.append(f"required_web_search_missing:{web_search_count}/2")
            if web_fetch_count < 1:
                hard_failures.append(f"required_web_fetch_missing:{web_fetch_count}/1")
    if execution_status == "ENFORCED_MISSING":
        hard_failures.append("research_execution_missing")
    open_topics = [name for name, present in topics.items() if not present]
    review_flags: list[str] = []
    if open_topics:
        review_flags.append("open_research_topics:" + ",".join(open_topics))
    if adjacency is not None and adjacency < 0.50:
        review_flags.append(f"numeric_claim_adjacency:{adjacency:.3f}")
    if source_quality < 0.60 and anchor_count:
        review_flags.append(f"source_identity_resolution:{source_quality:.3f}")
    if duplicate_ratio > 0.08:
        review_flags.append(f"duplicate_paragraph_ratio:{duplicate_ratio:.3f}")
    if filler_count > 3:
        review_flags.append(f"filler_phrases:{filler_count}")
    status = "FAIL" if hard_failures else "PASS"
    return {
        "chapter_index": chapter_index,
        "status": status,
        "closure": {
            "answered_topics": [name for name, present in topics.items() if present],
            "open_topics": open_topics,
            "topic_coverage": round(question_ratio, 4),
        },
        "signals": {
            "duplicate_ratio": round(duplicate_ratio, 4),
            "filler_phrase_count": filler_count,
            "unknown_sources": unresolved_count,
            "source_anchor_count": anchor_count,
            "source_identity_resolution": round(source_quality, 4),
            "unresolved_source_components": unresolved_count,
            "numeric_claim_lines": numeric_claims,
            "adjacent_evidence_claim_lines": adjacent_claims,
            "claim_evidence_adjacency": round(adjacency, 4) if adjacency is not None else None,
            "research_execution_status": execution_status,
            "missing_executed_sections": missing_executed_sections,
            "missing_research_topics": open_topics,
        },
        "hard_failures": hard_failures,
        "review_flags": review_flags,
        "warnings": [],
    }


def evaluate_absolute_quality(output_dir: str | Path, *, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    registry = EvidenceRegistry()
    registry.register_from_output_dir(str(output))
    research_execution = _load_research_execution(str(output))
    chapters = []
    for idx in range(15):
        path = _chapter_path(output, idx)
        if not path.exists():
            chapters.append({"chapter_index": idx, "status": "FAIL", "hard_failures": ["missing_file"], "review_flags": [], "warnings": []})
            continue
        chapters.append(score_chapter(
            path.read_text(encoding="utf-8"), idx, str(output), registry, research_execution
        ))
    failed = [item["chapter_index"] for item in chapters if item["status"] == "FAIL"]
    review_chapters = [item["chapter_index"] for item in chapters if item.get("review_flags")]
    critical_failed = sorted(set(failed).intersection(CRITICAL_CHAPTERS))
    report_status = "FAIL" if failed else "PASS"
    result = {
        "version": 3,
        "status": report_status,
        "scoring_policy": "no_compensating_score",
        "role": "research_execution_audit_and_review_priorities",
        "hard_contract_status": "FAIL" if failed else "PASS",
        "research_execution_status": (
            "ENFORCED" if research_execution.get("enforced") else
            "RECORDED" if research_execution.get("chapters") else "UNKNOWN"
        ),
        "failed_chapters": failed,
        "critical_failed_chapters": critical_failed,
        "warning_chapters": [],
        "review_chapters": review_chapters,
        "chapters": chapters,
    }
    if persist:
        json_path = output / "absolute_quality_scorecard.json"
        md_path = output / "absolute_quality_scorecard.md"
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(render_markdown(result), encoding="utf-8")
        result["json_path"] = str(json_path)
        result["markdown_path"] = str(md_path)
    return result


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# 研究执行审计与闭环诊断",
        "",
        "> 不计算总分或等级。硬失败只来自可客观验证的来源/研究执行问题；其余信号仅用于人工复核，不驱动扩写。",
        "",
        f"- 状态：**{result['status']}**",
        f"- 硬契约：**{result['hard_contract_status']}**",
        f"- 硬失败章节：{result['failed_chapters']}",
        f"- 人工复核优先章节：{result['review_chapters']}",
        "",
        "| 章节 | 硬状态 | 问题覆盖 | 开放问题 | 数字断言邻证 | 来源身份解析 | 研究执行 |",
        "|---:|---|---:|---|---:|---:|---|",
    ]
    for item in result["chapters"]:
        closure = item.get("closure", {})
        signals = item.get("signals", {})
        adjacency = signals.get("claim_evidence_adjacency")
        lines.append(
            f"| Ch{item['chapter_index']} | {item['status']} | {closure.get('topic_coverage', 0):.0%} | "
            f"{', '.join(closure.get('open_topics', [])) or '-'} | "
            f"{'N/A' if adjacency is None else f'{adjacency:.0%}'} | "
            f"{signals.get('source_identity_resolution', 0):.0%} | "
            f"{signals.get('research_execution_status', 'UNKNOWN')} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 v13 研究执行审计与闭环诊断")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = evaluate_absolute_quality(args.output_dir)
    print(json.dumps({key: result[key] for key in (
        "status", "hard_contract_status", "failed_chapters", "review_chapters"
    )}, ensure_ascii=False))
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
