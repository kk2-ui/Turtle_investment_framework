#!/usr/bin/env python3
"""Non-compensating V3 research-quality report and expression diagnostic."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_FILLER = re.compile(r"值得注意的是|不难发现|众所周知|显而易见|总体而言|综上所述|需要指出的是")
_SOURCE = re.compile(r"\[(?:table-)?source:\s*[^\]]+\]", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalise(text: str) -> str:
    text = _SOURCE.sub("", text)
    text = re.sub(r"[`*_>#|\-]", "", text)
    return re.sub(r"\s+|[，。；：、,.!?！？（）()]", "", text).strip().lower()


def evaluate_expression_efficiency(report_text: str) -> dict[str, Any]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", report_text) if part.strip()]
    prose = [item for item in paragraphs if not item.startswith("#") and len(_normalise(item)) >= 40]
    normalised = [_normalise(item) for item in prose]
    counts = Counter(normalised)
    duplicate_instances = sum(count - 1 for count in counts.values() if count > 1)
    duplicate_ratio = duplicate_instances / max(1, len(normalised))
    # Sentence length is a prose signal. Splitting the entire Markdown document
    # makes a multi-row table (which often contains no full stop) look like one
    # enormous sentence, so table/code/source-definition lines are excluded.
    prose_lines: list[str] = []
    fenced = False
    for raw in report_text.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not line or line.startswith(("#", "|", "---", "[^")):
            continue
        line = re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+)", "", line)
        prose_lines.append(line)
    sentences = [
        sentence.strip()
        for line in prose_lines
        for sentence in re.split(r"[。！？!?]", line)
        if len(_normalise(sentence)) >= 20
    ]
    long_sentences = sum(len(s) > 180 for s in sentences)
    filler_count = len(_FILLER.findall(report_text))
    findings: list[str] = []
    if duplicate_ratio > 0.08:
        findings.append(f"duplicate_paragraph_ratio:{duplicate_ratio:.3f}>0.080")
    if filler_count > max(3, len(sentences) // 80):
        findings.append(f"filler_phrases:{filler_count}")
    if long_sentences > max(5, len(sentences) // 12):
        findings.append(f"overlong_sentences:{long_sentences}")
    return {
        "status": "WARN" if findings else "PASS",
        "blocking": False,
        "metrics": {
            "prose_paragraphs": len(prose),
            "duplicate_instances": duplicate_instances,
            "duplicate_paragraph_ratio": round(duplicate_ratio, 4),
            "filler_phrase_count": filler_count,
            "sentence_count": len(sentences),
            "overlong_sentence_count": long_sentences,
        },
        "findings": findings,
    }


def _gate_state(value: dict[str, Any]) -> str:
    return str(value.get("state") or value.get("status") or "ERROR").upper()


def evaluate_v3_quality(
    output_dir: str | Path,
    report_text: str,
    *,
    gate_results: dict[str, dict[str, Any]],
    judgment_review: dict[str, Any] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    states = {name: _gate_state(value) for name, value in gate_results.items()}
    if "INVALID" in states.values() or "FAIL" in states.values() or "ERROR" in states.values():
        lifecycle = "INVALID"
    elif "INCOMPLETE" in states.values():
        lifecycle = "INCOMPLETE"
    elif states and all(state in {"DECISION_READY", "MONITORING", "REVIEWABLE", "SKIP", "PASS"} for state in states.values()):
        lifecycle = "DECISION_READY"
    else:
        lifecycle = "INCOMPLETE"
    expression = evaluate_expression_efficiency(report_text)
    result = {
        "schema_version": "v3-quality-report.v1",
        "generated_at": _now(),
        "status": lifecycle,
        "scoring_policy": "non_compensating_gates",
        "total_score": None,
        "layers": {
            "data_and_evidence": {"gate_states": {"official_evidence": states.get("official_evidence"), "claim_evidence": states.get("claim_evidence")}},
            "reasoning_and_competing_explanations": {"gate_states": {"decisive_questions": states.get("decisive_questions"), "base_rate": states.get("base_rate"), "claim_evidence": states.get("claim_evidence"), "thesis_test": states.get("thesis_test"), "insight": states.get("insight")}},
            "valuation_and_decision": {"gate_states": {"valuation_route": states.get("valuation_route"), "valuation": states.get("valuation"), "decision_reliability": states.get("decision_reliability"), "decision": states.get("decision"), "decision_compiler": states.get("decision_compiler")}},
            "judgment_ceiling": {
                "state": str((judgment_review or {}).get("state") or "NOT_ASSESSABLE"),
                "verdict": str((judgment_review or {}).get("ceiling_verdict") or "NOT_ASSESSABLE"),
                "blocking": False,
            },
            "expression_efficiency": {"status": expression["status"], "blocking": False},
        },
        "expression": expression,
        "policy_note": "Expression and judgment-ceiling reviews are diagnostic only and cannot offset or downgrade hard research gates.",
        "report_sha256": hashlib.sha256(report_text.encode("utf-8")).hexdigest(),
    }
    if persist:
        output = Path(output_dir)
        (output / "v3_quality_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = [
            "# V3 研究质量成绩单", "",
            f"- 发布状态：**{lifecycle}**", "- 计分方式：关键门控，不使用可抵消的总分", "",
            "| 分层 | 状态 | 是否阻断 |", "|---|---|---|",
            f"| 数据与证据 | {states.get('official_evidence')} / {states.get('claim_evidence')} | 是 |",
            f"| 推理、竞争解释与洞见 | {states.get('decisive_questions')} / base-rate={states.get('base_rate')} / {states.get('thesis_test')} / {states.get('insight')} | 是 |",
            f"| 估值路由与决策 | {states.get('valuation_route')} / {states.get('valuation')} / reliability={states.get('decision_reliability')} / {states.get('decision')} / compiler={states.get('decision_compiler')} | 是 |",
            f"| 洞见上限 | {str((judgment_review or {}).get('ceiling_verdict') or 'NOT_ASSESSABLE')} | 否 |",
            f"| 表达效率 | {expression['status']} | 否 |", "",
            "表达诊断与洞见上限评审不能抵消事实、口径、推理、估值或决策失败。",
        ]
        (output / "v3_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
