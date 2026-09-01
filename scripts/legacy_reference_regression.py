#!/usr/bin/env python3
"""Historical-reference regression for Turtle v13 chapter sets.

This is a regression diagnostic, not an absolute quality judge.  Text length,
topic recall and citation-count drift are warnings only.  Publication may be
blocked solely when a baseline ``core_fact_manifest.json`` contains a verified
fact that the candidate removes or changes without an explicit, sourced change
record.  Decision changes are governed by ``decision_diff.json``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

try:
    from scripts.chapter_depth import analyze_chapter_depth, detect_data_richness
    from scripts.research_plan import topic_presence
except ModuleNotFoundError:
    from chapter_depth import analyze_chapter_depth, detect_data_richness
    from research_plan import topic_presence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "config" / "legacy_reference_regression.json"
METRICS = ("substantive_chars", "analysis_lines", "derivation_lines", "evidence_anchors")


def _chapter_path(directory: Path, idx: int) -> Path:
    direct = directory / f"_ch{idx:02d}.md"
    if direct.exists():
        return direct
    return directory / "chapters" / f"_ch{idx:02d}.md"


def _ratio(value: int, baseline: int) -> float:
    if baseline <= 0:
        return 1.0
    return value / baseline


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _core_fact_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    facts = payload.get("facts") or []
    return {
        str(item.get("fact_id")): item
        for item in facts
        if isinstance(item, dict) and item.get("fact_id") and item.get("status", "verified") == "verified"
    }


def _derive_core_fact_manifest(directory: Path) -> dict[str, Any]:
    claims = _load_object(directory / "claim_evidence.json").get("claims") or []
    facts: dict[str, dict[str, Any]] = {}
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        for raw in claim.get("raw_facts") or []:
            if not isinstance(raw, dict) or not raw.get("evidence_id"):
                continue
            if not raw.get("direct_support") or raw.get("basis_match") not in {"exact", "compatible"}:
                continue
            fact_id = str(raw["evidence_id"])
            facts[fact_id] = {
                "fact_id": fact_id, "status": "verified", "identity": raw.get("fact"),
                "basis": raw.get("basis_match"), "period": raw.get("data_as_of"),
                "source_ids": [raw.get("source_id")] if raw.get("source_id") else [],
            }
    return {"schema_version": "core-fact-manifest.v1", "facts": list(facts.values())}


def _fact_identity(item: dict[str, Any]) -> dict[str, Any]:
    """Return only identity-bearing fields; prose and timestamps do not lock."""
    keys = ("identity", "canonical_value", "unit", "basis", "period", "source_ids")
    return {key: item.get(key) for key in keys if key in item}


def compare_core_facts(candidate_dir: Path, baseline_dir: Path) -> dict[str, Any]:
    baseline_path = baseline_dir / "core_fact_manifest.json"
    candidate_path = candidate_dir / "core_fact_manifest.json"
    changes_path = candidate_dir / "core_fact_changes.json"
    baseline_payload = _load_object(baseline_path) or _derive_core_fact_manifest(baseline_dir)
    baseline = _core_fact_map(baseline_payload)
    if not baseline:
        return {"status": "SKIP", "reason": "baseline core fact manifest missing or empty", "failures": []}
    candidate_payload = _load_object(candidate_path) or _derive_core_fact_manifest(candidate_dir)
    candidate = _core_fact_map(candidate_payload)
    changes_payload = _load_object(changes_path)
    changes = {
        str(item.get("fact_id")): item
        for item in (changes_payload.get("changes") or [])
        if isinstance(item, dict) and item.get("fact_id")
    }
    failures: list[str] = []
    accepted_changes: list[str] = []
    unchanged: list[str] = []
    for fact_id, old in baseline.items():
        new = candidate.get(fact_id)
        if new is not None and _fact_identity(new) == _fact_identity(old):
            unchanged.append(fact_id)
            continue
        change = changes.get(fact_id) or {}
        reason = str(change.get("change_reason") or "").strip()
        sources = change.get("source_ids") or change.get("replacement_source_ids") or []
        if reason and isinstance(sources, list) and any(str(source).strip() for source in sources):
            accepted_changes.append(fact_id)
            continue
        failure_kind = "missing" if new is None else "changed"
        failures.append(f"{fact_id}:{failure_kind}_without_sourced_change_reason")
    return {
        "status": "FAIL" if failures else "PASS",
        "baseline_path": str(baseline_path),
        "candidate_path": str(candidate_path),
        "changes_path": str(changes_path),
        "checked_fact_ids": sorted(baseline),
        "unchanged_fact_ids": sorted(unchanged),
        "accepted_change_fact_ids": sorted(accepted_changes),
        "failures": failures,
    }


def compare_chapter_sets(
    candidate_dir: str | Path,
    baseline_dir: str | Path,
    *,
    hard_floor: float = 0.55,
    warn_floor: float = 0.75,
    topic_hard_floor: float = 0.60,
    topic_warn_floor: float = 0.80,
) -> dict[str, Any]:
    candidate = Path(candidate_dir)
    baseline = Path(baseline_dir)
    rich = detect_data_richness(str(candidate.parent if candidate.name == "chapters" else candidate))
    chapters: list[dict[str, Any]] = []
    for idx in range(15):
        candidate_path = _chapter_path(candidate, idx)
        baseline_path = _chapter_path(baseline, idx)
        if not candidate_path.exists() or not baseline_path.exists():
            chapters.append({
                "chapter_index": idx,
                "status": "WARN",
                "missing": [
                    str(path) for path in (candidate_path, baseline_path) if not path.exists()
                ],
            })
            continue
        candidate_text = candidate_path.read_text(encoding="utf-8")
        baseline_text = baseline_path.read_text(encoding="utf-8")
        current = analyze_chapter_depth(candidate_text, idx, data_rich=rich)["metrics"]
        reference_metrics = analyze_chapter_depth(baseline_text, idx, data_rich=True)["metrics"]
        ratios = {name: round(_ratio(current[name], reference_metrics[name]), 4) for name in METRICS}
        reference_topics = topic_presence(baseline_text, idx)
        current_topics = topic_presence(candidate_text, idx)
        active_topics = [name for name, present in reference_topics.items() if present]
        retained_topics = [name for name in active_topics if current_topics.get(name)]
        topic_recall = len(retained_topics) / len(active_topics) if active_topics else 1.0
        # Historical prose is not a truth source.  Even a severe drop is a
        # visible warning; only compare_core_facts may create a hard failure.
        severe_warnings = [f"{name}:{value:.2f}<{hard_floor:.2f}" for name, value in ratios.items() if value < hard_floor]
        warnings = [f"{name}:{value:.2f}<{warn_floor:.2f}" for name, value in ratios.items() if hard_floor <= value < warn_floor]
        if topic_recall < topic_hard_floor:
            severe_warnings.append(f"topic_recall:{topic_recall:.2f}<{topic_hard_floor:.2f}")
        elif topic_recall < topic_warn_floor:
            warnings.append(f"topic_recall:{topic_recall:.2f}<{topic_warn_floor:.2f}")
        warnings = severe_warnings + warnings
        status = "WARN" if warnings else "PASS"
        chapters.append({
            "chapter_index": idx,
            "status": status,
            "candidate_path": str(candidate_path),
            "baseline_path": str(baseline_path),
            "metrics": current,
            "reference_metrics": reference_metrics,
            "retention_ratios": ratios,
            "topic_recall": round(topic_recall, 4),
            "retained_topics": retained_topics,
            "missing_topics": [name for name in active_topics if name not in retained_topics],
            "hard_failures": [],
            "severe_warnings": severe_warnings,
            "warnings": warnings,
        })
    core_facts = compare_core_facts(candidate, baseline)
    failed = []
    warned = [item["chapter_index"] for item in chapters if item["status"] == "WARN"]
    status = "FAIL" if core_facts["status"] == "FAIL" else "WARN" if warned else "PASS"
    return {
        "version": 2,
        "status": status,
        "candidate_dir": str(candidate),
        "baseline_dir": str(baseline),
        "thresholds": {
            "hard_floor": hard_floor,
            "warn_floor": warn_floor,
            "topic_hard_floor": topic_hard_floor,
            "topic_warn_floor": topic_warn_floor,
        },
        "failed_chapters": failed,
        "warning_chapters": warned,
        "core_fact_status": core_facts["status"],
        "core_fact_failures": core_facts.get("failures", []),
        "core_facts": core_facts,
        "decision_diff_path": str(candidate / "decision_diff.json"),
        "chapters": chapters,
    }


def _stock_code(output_dir: Path) -> str:
    contract = output_dir / "analysis_contract.json"
    try:
        payload = json.loads(contract.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    raw = str(payload.get("ts_code") or output_dir.name.split("_", 1)[0])
    return raw.split(".", 1)[0].zfill(6) if raw.isdigit() else raw.split(".", 1)[0]


def evaluate_from_config(
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
    *,
    persist: bool = True,
) -> dict[str, Any]:
    output = Path(output_dir)
    path = Path(config_path)
    if not path.exists():
        return {"status": "SKIP", "reason": "legacy reference config missing"}
    config = json.loads(path.read_text(encoding="utf-8"))
    code = _stock_code(output)
    spec = (config.get("references") or config.get("baselines") or {}).get(code)
    if not config.get("enabled", False) or not spec:
        return {"status": "SKIP", "reason": f"no legacy reference for {code}", "code": code}
    baseline = Path(spec["chapter_dir"])
    if not baseline.is_absolute():
        baseline = REPO_ROOT / baseline
    result = compare_chapter_sets(
        output,
        baseline,
        hard_floor=float(spec.get("hard_floor", config.get("hard_floor", 0.55))),
        warn_floor=float(spec.get("warn_floor", config.get("warn_floor", 0.75))),
        topic_hard_floor=float(spec.get("topic_hard_floor", config.get("topic_hard_floor", 0.60))),
        topic_warn_floor=float(spec.get("topic_warn_floor", config.get("topic_warn_floor", 0.80))),
    )
    result["code"] = code
    result["reference_name"] = spec.get("name", code)
    if persist:
        json_path = output / "legacy_reference_regression.json"
        md_path = output / "legacy_reference_regression.md"
        json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(render_markdown(result), encoding="utf-8")
        result["json_path"] = str(json_path)
        result["markdown_path"] = str(md_path)
    return result


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# 历史参考防退化回归",
        "",
        f"- 状态：**{result.get('status', 'UNKNOWN')}**",
        f"- 历史参考：{result.get('reference_name') or result.get('baseline_dir', '')}",
        f"- 硬失败章节：{result.get('failed_chapters', [])}",
        f"- 警告章节：{result.get('warning_chapters', [])}",
        "",
        "| 章节 | 状态 | 字符保留 | 分析保留 | 推导保留 | 证据保留 | 主题召回 | 缺失主题 |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in result.get("chapters", []):
        ratios = item.get("retention_ratios", {})
        lines.append(
            f"| Ch{item['chapter_index']} | {item.get('status')} | "
            f"{ratios.get('substantive_chars', 0):.0%} | {ratios.get('analysis_lines', 0):.0%} | "
            f"{ratios.get('derivation_lines', 0):.0%} | {ratios.get('evidence_anchors', 0):.0%} | "
            f"{item.get('topic_recall', 0):.0%} | {', '.join(item.get('missing_topics', [])) or '-'} |"
        )
    lines.extend([
        "", "## 核心事实保护", "",
        f"- 状态：**{result.get('core_fact_status', 'SKIP')}**",
        f"- 未解释的核心事实变化：{result.get('core_fact_failures', []) or '无'}",
        f"- 决策变更记录：`{result.get('decision_diff_path', '')}`",
        "", "## 判定说明", "",
        "全文长度、推导数量、证据数量及主题召回只用于发现可能的信息损失，始终为 WARN。只有显式登记且已验证的核心事实，在无变更理由和新来源时被删除或改值，才会 FAIL。决策变化由 decision ledger diff 管理，不以旧稿相似度锁定。",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 v13 历史参考防退化回归")
    parser.add_argument("--candidate-dir", required=True)
    parser.add_argument("--baseline-dir", default="")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    if args.baseline_dir:
        result = compare_chapter_sets(args.candidate_dir, args.baseline_dir)
        output = Path(args.output or Path(args.candidate_dir) / "legacy_reference_regression.json")
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        output.with_suffix(".md").write_text(render_markdown(result), encoding="utf-8")
    else:
        result = evaluate_from_config(args.candidate_dir, args.config)
    print(json.dumps({key: result.get(key) for key in ("status", "failed_chapters", "warning_chapters", "json_path", "markdown_path")}, ensure_ascii=False))
    return 1 if result.get("status") == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
