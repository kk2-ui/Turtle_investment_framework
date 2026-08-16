"""写作工具集 — 写章节、读章节、审计、组装报告。

对接现有 Python 模块：
- ``audit_rules.py`` — S1/E1/C1/C2/S2 审计规则
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_scripts_dir = os.path.join(os.path.dirname(__file__), "..", "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

try:
    from turtle_agent._version import REPORT_VERSION, CHAPTERS_SUBDIR, REPORTS_SUBDIR
except ImportError:
    REPORT_VERSION = "v13"
    CHAPTERS_SUBDIR = "chapters"
    REPORTS_SUBDIR  = "reports"

try:
    from scripts.chapter_depth import analyze_chapter_depth, depth_failure_description, detect_data_richness
except ModuleNotFoundError:
    from chapter_depth import analyze_chapter_depth, depth_failure_description, detect_data_richness  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# 写作工具
# ---------------------------------------------------------------------------

# 追踪每个章节文件的写入尝试。尝试次数只用于诊断；质量门不会因重试耗尽而放宽。
_write_attempt_counts: dict[str, int] = {}

_DECISION_DISPLAY_LABELS = {
    ("continue", "buy"): "Strong Buy",
    ("continue", "hold"): "Cautious Watch",
    ("continue", "avoid"): "好公司太贵",
    ("pause", "buy"): "价格错配",
    ("pause", "hold"): "Hold Review",
    ("pause", "avoid"): "Likely Avoid",
    ("abandon", "buy"): "数据冲突",
    ("abandon", "hold"): "Slow Fade",
    ("abandon", "avoid"): "Strong Reject",
}

_CANONICAL_CHAPTER_TITLES = {
    0: "投资要点概览", 1: "公司做的是什么生意", 2: "行业吸引力与公司位置",
    3: "商业模式机制、护城河与关键约束", 4: "最近一年关键变化与当前阶段",
    5: "经营表现与核心驱动", 6: "财务表现与资本配置", 7: "股东回报路径",
    8: "管理层、治理与激励", 9: "核心风险与否决项", 10: "增长质量与参数校准",
    11: "穿透回报率 GG", 12: "内在价值合成与裁决", 13: "DDM 估值与仓位执行",
    14: "综合决策",
}


def verify_official_fact(
    output_dir: str = ".",
    doc_id: str = "",
    page: int = 0,
    fact_name: str = "",
    domain: str = "",
    raw_value: Any = None,
    normalized_value: Any = None,
    unit: str = "",
    basis: str = "",
    quote: str = "",
    currency: str | None = None,
) -> dict[str, Any]:
    """Verify an exact annual-report quote and persist its observation identity."""
    try:
        from scripts.evidence_facts import verify_fact_from_quote
        from scripts.build_report_context import build_verified_context
    except ModuleNotFoundError:
        from evidence_facts import verify_fact_from_quote
        from build_report_context import build_verified_context
    result = verify_fact_from_quote(
        output_dir,
        doc_id=doc_id,
        page=int(page),
        fact_name=fact_name,
        domain=domain,
        raw_value=raw_value,
        normalized_value=normalized_value,
        unit=unit,
        basis=basis,
        quote=quote,
        currency=currency,
    )
    if not result.get("verified"):
        return result
    output = Path(output_dir)
    manifest = json.loads((output / "document_manifest.json").read_text(encoding="utf-8"))
    facts = json.loads((output / "fact_observations.json").read_text(encoding="utf-8"))
    context = build_verified_context(output, manifest, facts, persist=True)
    result["context_fingerprint"] = context["meta"]["context_fingerprint"]
    return result


def _ensure_canonical_chapter_heading(content: str, chapter_index: int) -> str:
    """Make report identity deterministic instead of relying on model styling."""
    title = _CANONICAL_CHAPTER_TITLES.get(int(chapter_index))
    if title is None:
        return content
    canonical = f"## Ch{int(chapter_index)} {title}"
    text = str(content or "").lstrip("\ufeff\n ")
    first_h2 = re.search(r"^##\s+[^\n]+", text, flags=re.MULTILINE)
    if first_h2:
        return text[:first_h2.start()] + canonical + text[first_h2.end():]
    return canonical + "\n\n" + text


def write_decision_manifest(
    output_dir: str = ".",
    qualitative_decision: str = "",
    quantitative_decision: str = "",
    position_pct: float = 0.0,
    qualitative_rationale: str = "",
    quantitative_rationale: str = "",
    monitor_triggers: list[str] | None = None,
    exit_conditions: list[str] | None = None,
) -> dict[str, Any]:
    """Commit the report decision as structured data before assembly."""
    qual = str(qualitative_decision).strip().lower()
    quant = str(quantitative_decision).strip().lower()
    if qual not in {"continue", "pause", "abandon"}:
        return {"error": f"invalid qualitative_decision: {qual!r}"}
    if quant not in {"buy", "hold", "avoid"}:
        return {"error": f"invalid quantitative_decision: {quant!r}"}
    try:
        from scripts.unified_decision_synthesizer import UnifiedDecisionInput, synthesize_decision
    except ModuleNotFoundError:
        from unified_decision_synthesizer import UnifiedDecisionInput, synthesize_decision

    raw_position = max(0.0, float(position_pct or 0.0))
    synthesized = synthesize_decision(UnifiedDecisionInput(
        qualitative_decision=qual,
        quantitative_decision=quant,
        qualitative_rationale=qualitative_rationale,
        quantitative_rationale=quantitative_rationale,
        position_pct=raw_position,
        monitor_triggers=list(monitor_triggers or []),
        exit_conditions=list(exit_conditions or []),
    )).to_dict()
    unified_value = getattr(synthesized.get("unified_decision"), "value", synthesized.get("unified_decision"))
    display_label = _DECISION_DISPLAY_LABELS[(qual, quant)]
    family = {
        "strong_buy": "Strong Buy",
        "buy": "Buy",
        "hold": "Hold",
        "avoid": "Avoid",
        "strong_reject": "Strong Reject",
    }.get(str(unified_value), "Hold")
    manifest = {
        "schema_version": "decision-manifest.v1",
        "qualitative_decision": qual,
        "quantitative_decision": quant,
        "unified_decision": str(unified_value),
        "display_label": display_label,
        "decision_family": family,
        # 观察仓也属于报告承诺，不能被旧 synthesizer 的 buy-only 仓位规则吞掉。
        "position_pct": raw_position,
        "consistency_note": synthesized.get("consistency_note", ""),
        "rationales": synthesized.get("rationales", []),
        "monitor_triggers": list(monitor_triggers or []),
        "exit_conditions": list(exit_conditions or []),
    }
    ledger_path = Path(output_dir) / "decision_ledger.json"
    try:
        existing_ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        existing_ledger = {}
    existing_freeze = existing_ledger.get("freeze") if isinstance(existing_ledger, dict) else None
    if isinstance(existing_freeze, dict) and existing_freeze.get("frozen"):
        frozen_decision = existing_ledger.get("decision") or {}
        decision_fields = {
            key: manifest.get(key)
            for key in (
                "qualitative_decision", "quantitative_decision", "unified_decision",
                "display_label", "decision_family", "position_pct",
            )
        }
        if frozen_decision != decision_fields:
            return {
                "written": False,
                "decision_frozen": True,
                "error": "frozen decision_ledger rejected decision_manifest drift",
                "existing_decision": frozen_decision,
                "attempted_decision": decision_fields,
            }
    path = os.path.join(output_dir, "decision_manifest.json")
    Path(path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": path, "manifest": manifest}


def write_decision_ledger(
    output_dir: str = ".",
    entries: list[dict[str, Any]] | None = None,
    change_reason: str = "",
    freeze: bool = True,
) -> dict[str, Any]:
    """Persist V3 canonical decision metrics after the decision manifest.

    Frozen ledgers accept idempotent writes only.  The LLM-facing tool never
    exposes the internal override needed for a real decision revision.
    """
    try:
        from scripts.decision_ledger import build_decision_ledger, persist_decision_ledger, bind_decision_references, evaluate_output_decision_ledger, promote_reviewable_decision_ledger
    except ModuleNotFoundError:
        from decision_ledger import build_decision_ledger, persist_decision_ledger, bind_decision_references, evaluate_output_decision_ledger, promote_reviewable_decision_ledger

    chapter_dir = Path(output_dir) / CHAPTERS_SUBDIR
    if not chapter_dir.is_dir():
        chapter_dir = Path(output_dir)
    report_text = "\n\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(chapter_dir.glob("_ch*.md"))
    )
    payload = build_decision_ledger(
        output_dir,
        list(entries or []),
        change_reason=str(change_reason or "").strip(),
        # Binding canonical IDs beside repeated values is deterministic and
        # happens after persistence.  Therefore a requested final write first
        # lands as a reviewable draft, then binds, validates and freezes.
        freeze=False,
    )
    result = persist_decision_ledger(
        output_dir,
        payload,
        report_text=report_text,
        allow_frozen_update=False,
    )
    if result.get("written"):
        binding = bind_decision_references(output_dir, result.get("ledger") or payload)
        chapter_dir = Path(output_dir) / CHAPTERS_SUBDIR
        if not chapter_dir.is_dir(): chapter_dir = Path(output_dir)
        rebound_text = "\n\n".join(path.read_text(encoding="utf-8") for path in sorted(chapter_dir.glob("_ch*.md")))
        validation = evaluate_output_decision_ledger(output_dir, report_text=rebound_text, persist=True)
        result["binding"] = binding
        result["validation"] = validation
        if freeze:
            promotion = promote_reviewable_decision_ledger(
                output_dir,
                report_text=rebound_text,
            )
            result["promotion"] = promotion
            result["validation"] = evaluate_output_decision_ledger(
                output_dir,
                report_text=rebound_text,
                persist=True,
            )
    return result


def write_claim_evidence_ledger(
    output_dir: str = ".",
    claims: list[dict[str, Any]] | None = None,
    change_reason: str = "",
    freeze: bool = True,
    repair_invalid_frozen: bool = False,
    resume_last_rejected: bool = False,
    drop_evidence_ids: list[str] | None = None,
    claim_chapter_additions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Persist the V3 major-claim evidence graph after report chapters exist."""
    try:
        from scripts.claim_evidence import build_claim_evidence_ledger, persist_claim_evidence_ledger, bind_claim_references, promote_reviewable_claim_evidence, evaluate_output_claim_evidence
    except ModuleNotFoundError:
        from claim_evidence import build_claim_evidence_ledger, persist_claim_evidence_ledger, bind_claim_references, promote_reviewable_claim_evidence, evaluate_output_claim_evidence

    effective_claims = list(claims or [])
    if resume_last_rejected:
        try:
            rejected = json.loads(
                Path(output_dir, "claim_evidence_last_rejected.json").read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, json.JSONDecodeError):
            return {
                "written": False,
                "error": "claim_evidence_last_rejected.json missing or invalid",
            }
        effective_claims = list(rejected.get("claims") or [])
    drops = {str(item) for item in (drop_evidence_ids or []) if str(item)}
    additions = {
        str(item.get("claim_id")): {
            int(chapter) for chapter in (item.get("chapters") or [])
        }
        for item in (claim_chapter_additions or [])
        if isinstance(item, dict) and item.get("claim_id")
    }
    if drops or additions:
        for claim in effective_claims:
            if drops:
                claim["raw_facts"] = [
                    item for item in (claim.get("raw_facts") or [])
                    if str(item.get("evidence_id") or "") not in drops
                ]
            claim_id = str(claim.get("claim_id") or "")
            if claim_id in additions:
                claim["chapters"] = sorted(
                    {int(item) for item in (claim.get("chapters") or [])}
                    | additions[claim_id]
                )

    chapter_dir = Path(output_dir) / CHAPTERS_SUBDIR
    if not chapter_dir.is_dir():
        chapter_dir = Path(output_dir)
    report_text = "\n\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(chapter_dir.glob("_ch*.md"))
    )
    payload = build_claim_evidence_ledger(
        output_dir,
        effective_claims,
        change_reason=str(change_reason or "").strip(),
        freeze=False,
    )
    result = persist_claim_evidence_ledger(
        output_dir,
        payload,
        report_text=report_text,
        allow_frozen_update=bool(repair_invalid_frozen),
    )
    if result.get("written"):
        result["binding"] = bind_claim_references(output_dir, result.get("ledger") or payload)
        # Canonical claim text can itself repeat decision-changing values.
        # Rebind the already-frozen decision IDs after inserting that text.
        try:
            from scripts.decision_ledger import bind_decision_references
        except ModuleNotFoundError:
            from decision_ledger import bind_decision_references
        decision_path = Path(output_dir) / "decision_ledger.json"
        if decision_path.is_file():
            decision_payload = json.loads(decision_path.read_text(encoding="utf-8"))
            result["decision_rebinding"] = bind_decision_references(
                output_dir, decision_payload
            )
        rebound_text = "\n\n".join(path.read_text(encoding="utf-8") for path in sorted(chapter_dir.glob("_ch*.md")))
        if freeze:
            result["promotion"] = promote_reviewable_claim_evidence(output_dir, report_text=rebound_text)
        result["validation"] = evaluate_output_claim_evidence(output_dir, report_text=rebound_text, persist=True)
    return result


def write_valuation_model_ledger(
    output_dir: str = ".",
    company_profile: dict[str, Any] | None = None,
    models: list[dict[str, Any]] | None = None,
    synthesis: dict[str, Any] | None = None,
    cash_access_bridge: dict[str, Any] | None = None,
    parameter_calibrations: list[dict[str, Any]] | None = None,
    model_comparisons: list[dict[str, Any]] | None = None,
    joint_stress_tests: list[dict[str, Any]] | None = None,
    action_policy: dict[str, Any] | None = None,
    semantic_resolutions: list[dict[str, Any]] | None = None,
    resume_best_rejected: bool = False,
    resume_last_rejected: bool = False,
    semantic_resolution_patches: list[dict[str, Any]] | None = None,
    change_reason: str = "",
    freeze: bool = True,
    repair_invalid_frozen: bool = False,
) -> dict[str, Any]:
    """Persist the V3 valuation applicability and fragility ledger."""
    try:
        from scripts.valuation_model_gate import build_valuation_model_ledger, persist_valuation_model_ledger, bind_valuation_references, promote_reviewable_valuation_model, evaluate_output_valuation_model, valuation_fingerprint, validate_valuation_model_ledger, record_rejected_valuation_candidate
        from scripts.valuation_model_migration import validate_valuation_semantic_research
    except ModuleNotFoundError:
        from valuation_model_gate import build_valuation_model_ledger, persist_valuation_model_ledger, bind_valuation_references, promote_reviewable_valuation_model, evaluate_output_valuation_model, valuation_fingerprint, validate_valuation_model_ledger, record_rejected_valuation_candidate
        from valuation_model_migration import validate_valuation_semantic_research
    effective_company_profile = dict(company_profile or {})
    effective_models = list(models or [])
    effective_synthesis = dict(synthesis or {})
    effective_cash_access_bridge = dict(cash_access_bridge or {})
    effective_parameter_calibrations = list(parameter_calibrations or [])
    effective_model_comparisons = list(model_comparisons or [])
    effective_joint_stress_tests = list(joint_stress_tests or [])
    effective_action_policy = dict(action_policy or {})
    effective_resolutions = list(semantic_resolutions or [])
    if resume_best_rejected and resume_last_rejected:
        return {
            "written": False,
            "error": "semantic and reliability rejected-draft resume modes are mutually exclusive",
        }
    if resume_last_rejected:
        best_envelope_path = Path(output_dir, "valuation_model_best_rejected.json")
        try:
            best_envelope = json.loads(best_envelope_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            best_envelope = {}
        rejected_path = Path(output_dir, "valuation_model_last_rejected.json")
        try:
            rejected = (
                best_envelope.get("candidate")
                if isinstance(best_envelope.get("candidate"), dict)
                else json.loads(rejected_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError):
            return {
                "written": False,
                "path": str(Path(output_dir) / "valuation_model.json"),
                "error": "valuation_model_last_rejected.json missing or invalid",
                "resume_rejected": True,
            }
        if not isinstance(rejected, dict) or not rejected.get("models"):
            return {
                "written": False,
                "path": str(Path(output_dir) / "valuation_model.json"),
                "error": "last rejected valuation draft has no complete model set",
                "resume_rejected": True,
            }
        if models is not None:
            base_model_ids = {
                str(item.get("model_id") or "") for item in rejected.get("models") or []
                if isinstance(item, dict) and item.get("model_id")
            }
            submitted_model_ids = {
                str(item.get("model_id") or "") for item in models
                if isinstance(item, dict) and item.get("model_id")
            }
            if submitted_model_ids != base_model_ids:
                return {
                    "written": False,
                    "path": str(Path(output_dir) / "valuation_model.json"),
                    "error": "resume models must preserve the exact complete model_id set",
                    "missing_model_ids": sorted(base_model_ids - submitted_model_ids),
                    "unexpected_model_ids": sorted(submitted_model_ids - base_model_ids),
                    "resume_rejected": True,
                }
        # Omitted arguments preserve the rejected candidate.  Explicit
        # sections replace whole top-level contracts and are fully revalidated.
        effective_company_profile = dict(
            (rejected.get("company_profile") if company_profile is None else company_profile) or {}
        )
        effective_models = list((rejected.get("models") if models is None else models) or [])
        effective_synthesis = dict((rejected.get("synthesis") if synthesis is None else synthesis) or {})
        effective_cash_access_bridge = dict(
            (rejected.get("cash_access_bridge")
            if cash_access_bridge is None else cash_access_bridge) or {}
        )
        effective_parameter_calibrations = list(
            (rejected.get("parameter_calibrations")
            if parameter_calibrations is None else parameter_calibrations) or []
        )
        effective_model_comparisons = list(
            (rejected.get("model_comparisons")
            if model_comparisons is None else model_comparisons) or []
        )
        effective_joint_stress_tests = list(
            (rejected.get("joint_stress_tests")
            if joint_stress_tests is None else joint_stress_tests) or []
        )
        effective_action_policy = dict(
            (rejected.get("action_policy") if action_policy is None else action_policy) or {}
        )
    if resume_best_rejected:
        best_path = Path(output_dir, "valuation_semantic_resolution_best_rejected.json")
        try:
            best = json.loads(best_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            best = {}
        migration_report_path = Path(output_dir, "valuation_model_migration_report.json")
        try:
            migration_report = json.loads(migration_report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            migration_report = {}
        best_candidate = best.get("candidate") if isinstance(best.get("candidate"), dict) else {}
        frontier_keys = {
            (str(item.get("model_id") or ""), str(item.get("field") or ""))
            for item in migration_report.get("semantic_frontier") or [] if isinstance(item, dict)
        }
        best_resolutions = best.get("resolutions") or []
        best_keys = {
            (str(item.get("model_id") or ""), str(item.get("field") or ""))
            for item in best_resolutions if isinstance(item, dict)
        }
        source_matches = (
            not best.get("source_ledger_fingerprint")
            or best.get("source_ledger_fingerprint") == migration_report.get("source_ledger_fingerprint")
        )
        if not best_candidate or not frontier_keys or best_keys != frontier_keys or not source_matches:
            return {
                "written": False,
                "path": str(Path(output_dir) / "valuation_model.json"),
                "error": "best rejected valuation draft is missing or stale; reread valuation contract",
                "resume_rejected": True,
            }
        patch_map: dict[tuple[str, str], dict[str, Any]] = {}
        for item in semantic_resolution_patches or []:
            if not isinstance(item, dict):
                continue
            key = (str(item.get("model_id") or ""), str(item.get("field") or ""))
            if key not in frontier_keys:
                return {
                    "written": False,
                    "path": str(Path(output_dir) / "valuation_model.json"),
                    "error": f"semantic resolution patch is outside frontier: {key[0]}:{key[1]}",
                    "resume_rejected": True,
                }
            patch_map[key] = item
        merged = {
            (str(item.get("model_id") or ""), str(item.get("field") or "")): item
            for item in best_resolutions if isinstance(item, dict)
        }
        merged.update(patch_map)
        effective_company_profile = dict(best_candidate.get("company_profile") or {})
        effective_models = list(best_candidate.get("models") or [])
        effective_synthesis = dict(best_candidate.get("synthesis") or {})
        effective_cash_access_bridge = dict(best_candidate.get("cash_access_bridge") or {})
        effective_parameter_calibrations = list(best_candidate.get("parameter_calibrations") or [])
        effective_model_comparisons = list(best_candidate.get("model_comparisons") or [])
        effective_joint_stress_tests = list(best_candidate.get("joint_stress_tests") or [])
        effective_action_policy = dict(best_candidate.get("action_policy") or {})
        effective_resolutions = [merged[key] for key in sorted(frontier_keys)]

    payload = build_valuation_model_ledger(
        output_dir, effective_company_profile, effective_models, effective_synthesis,
        change_reason=str(change_reason or "").strip(), freeze=False,
        cash_access_bridge=effective_cash_access_bridge,
        parameter_calibrations=effective_parameter_calibrations,
        model_comparisons=effective_model_comparisons,
        joint_stress_tests=effective_joint_stress_tests,
        action_policy=effective_action_policy,
    )
    chapter_dir = Path(output_dir) / CHAPTERS_SUBDIR
    if not chapter_dir.is_dir(): chapter_dir = Path(output_dir)
    report_text = "\n\n".join(path.read_text(encoding="utf-8") for path in sorted(chapter_dir.glob("_ch*.md")))
    semantic_validation = validate_valuation_semantic_research(
        output_dir, payload, effective_resolutions
    )
    if semantic_validation.get("state") not in {"NOT_REQUIRED", "REVIEWABLE"}:
        last_path = Path(output_dir, "valuation_semantic_resolution_last_rejected.json")
        semantic_candidate_path = Path(output_dir, "valuation_model_semantic_candidate.json")
        try:
            previous_last = json.loads(last_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous_last = {}
        if previous_last and not isinstance(previous_last.get("candidate"), dict):
            try:
                previous_last["candidate"] = json.loads(
                    semantic_candidate_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                pass
        migration_report_path = Path(output_dir, "valuation_model_migration_report.json")
        try:
            migration_report = json.loads(migration_report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            migration_report = {}
        rejected = {
            "schema_version": "valuation-semantic-research.v1",
            "source_ledger_fingerprint": migration_report.get("source_ledger_fingerprint"),
            "candidate": payload,
            "resolutions": effective_resolutions,
            "validation": semantic_validation,
        }
        semantic_candidate_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        last_path.write_text(
            json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        best_path = Path(output_dir, "valuation_semantic_resolution_best_rejected.json")
        try:
            best = json.loads(best_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            best = previous_last

        def rejection_score(item: dict[str, Any]) -> tuple[int, int, int, int]:
            validation = item.get("validation") if isinstance(item.get("validation"), dict) else {}
            invalid = validation.get("invalid_findings") or []
            incomplete = validation.get("incomplete_findings") or []
            missing = sum("semantic_resolution_missing:" in str(finding) for finding in incomplete)
            verified = validation.get("verified_evidence_ids") or []
            return len(invalid), missing, len(incomplete), -len(verified)

        winner = rejected if not best or rejection_score(rejected) < rejection_score(best) else best
        if winner:
            best_path.write_text(
                json.dumps(winner, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return {
            "written": False,
            "path": str(Path(output_dir) / "valuation_model.json"),
            "validation": semantic_validation,
            "semantic_validation": semantic_validation,
            "error": "valuation semantic frontier requires verified, exactly-scoped research",
        }
    # Decision reliability is non-compensating and therefore must be checked
    # before the candidate can replace even a reviewable canonical ledger.
    # Previously a structurally valid but reliability-invalid payload was
    # persisted first and rejected only afterwards.
    try:
        from scripts.decision_reliability import validate_decision_reliability
    except ModuleNotFoundError:
        from decision_reliability import validate_decision_reliability
    try:
        reliability_policy = json.loads(
            Path(output_dir, "decision_reliability_policy.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        reliability_policy = {}
    reliability_enforced = bool(reliability_policy.get("enforced"))
    reliability_validation = validate_decision_reliability(
        output_dir, report_text=report_text, enforced=reliability_enforced,
        valuation_override=payload,
    )
    if reliability_enforced and reliability_validation.get("state") not in {"DECISION_READY", "MONITORING"}:
        structural_validation = validate_valuation_model_ledger(
            payload, output_dir=output_dir, report_text=report_text, enforced=True,
        )
        record_rejected_valuation_candidate(
            output_dir, payload, report_text=report_text,
            structural_validation=structural_validation,
            reliability_validation=reliability_validation,
        )
        return {
            "written": False,
            "path": str(Path(output_dir) / "valuation_model.json"),
            "validation": reliability_validation,
            "structural_validation": structural_validation,
            "decision_reliability": reliability_validation,
            "error": "decision reliability validation failed before canonical persistence",
        }
    structural_validation = validate_valuation_model_ledger(
        payload, output_dir=output_dir, report_text=report_text, enforced=True,
    )
    decision_revision_findings = {
        "synthesis_manifest_action_mismatch",
        "synthesis_manifest_position_mismatch",
        "synthesis_v_final_mismatch",
    }
    structural_invalid = set(structural_validation.get("invalid_findings") or [])
    if (
        reliability_enforced
        and reliability_validation.get("state") in {"DECISION_READY", "MONITORING"}
        and structural_invalid
        and structural_invalid.issubset(decision_revision_findings)
        and not structural_validation.get("incomplete_findings")
    ):
        try:
            from scripts.decision_ledger import ledger_fingerprint
        except ModuleNotFoundError:
            from decision_ledger import ledger_fingerprint
        try:
            decision_ledger = json.loads(
                Path(output_dir, "decision_ledger.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            decision_ledger = {}
        try:
            decision_manifest = json.loads(
                Path(output_dir, "decision_manifest.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            decision_manifest = {}
        proposal = {
            "schema_version": "valuation-decision-revision-proposal.v1",
            "state": "INTERNAL_SYNTHESIS_REQUIRED",
            "candidate_fingerprint": valuation_fingerprint(payload),
            "current_decision_ledger_fingerprint": (
                ledger_fingerprint(decision_ledger) if decision_ledger else None
            ),
            "current_manifest": decision_manifest,
            "proposed_synthesis": payload.get("synthesis") or {},
            "required_revisions": sorted(structural_invalid),
            "candidate": payload,
            "structural_validation": structural_validation,
            "decision_reliability_validation": reliability_validation,
            # A valuation-layer action is an internal hypothesis, not a user
            # approval surface.  Human review belongs after thesis, insight,
            # chapter propagation and the full completion contract close.
            "approval_status": "NOT_REQUESTED_AT_VALUATION_STAGE",
            "review_scope": "FULL_REPORT_PHILOSOPHY_ALIGNMENT",
        }
        proposal_path = Path(output_dir, "valuation_decision_revision_proposal.json")
        proposal_path.write_text(
            json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        record_rejected_valuation_candidate(
            output_dir, payload, report_text=report_text,
            structural_validation=structural_validation,
            reliability_validation=reliability_validation,
        )
        return {
            "written": False,
            "decision_revision_proposed": True,
            "full_report_synthesis_required": True,
            "proposal_path": str(proposal_path),
            "proposal_state": proposal["state"],
            "candidate_fingerprint": proposal["candidate_fingerprint"],
            "validation": structural_validation,
            "decision_reliability": reliability_validation,
            "error": "valuation hypothesis changes canonical decision; complete full-report synthesis before final review",
        }
    result = persist_valuation_model_ledger(
        output_dir, payload, report_text=report_text,
        allow_frozen_update=bool(repair_invalid_frozen),
    )
    if result.get("written"):
        if semantic_validation.get("state") == "REVIEWABLE":
            Path(output_dir, "valuation_semantic_resolution.json").write_text(
                json.dumps({
                    "schema_version": "valuation-semantic-research.v1",
                    "valuation_fingerprint": valuation_fingerprint(result.get("ledger") or payload),
                    "resolutions": effective_resolutions,
                    "validation": semantic_validation,
                }, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        result["binding"] = bind_valuation_references(output_dir, result.get("ledger") or payload)
        rebound_text = "\n\n".join(path.read_text(encoding="utf-8") for path in sorted(chapter_dir.glob("_ch*.md")))
        if freeze:
            result["promotion"] = promote_reviewable_valuation_model(output_dir, report_text=rebound_text)
        result["validation"] = evaluate_output_valuation_model(output_dir, report_text=rebound_text, persist=True)
        try:
            from scripts.decision_reliability import evaluate_output_decision_reliability
        except ModuleNotFoundError:
            from decision_reliability import evaluate_output_decision_reliability
        result["decision_reliability"] = evaluate_output_decision_reliability(
            output_dir, report_text=rebound_text, persist=True
        )
        result["semantic_validation"] = semantic_validation
    return result


def write_thesis_test_ledger(
    output_dir: str = ".",
    competitive_tests: list[dict[str, Any]] | None = None,
    thresholds: list[dict[str, Any]] | None = None,
    probability_sets: list[dict[str, Any]] | None = None,
    change_reason: str = "",
    freeze: bool = True,
    repair_invalid_frozen: bool = False,
) -> dict[str, Any]:
    """Persist V3 competitive explanations, justified thresholds and probabilities."""
    try:
        from scripts.thesis_test_gate import build_thesis_test_ledger, persist_thesis_test_ledger, bind_thesis_test_references, promote_reviewable_thesis_test, evaluate_output_thesis_test
    except ModuleNotFoundError:
        from thesis_test_gate import build_thesis_test_ledger, persist_thesis_test_ledger, bind_thesis_test_references, promote_reviewable_thesis_test, evaluate_output_thesis_test
    chapter_dir = Path(output_dir) / CHAPTERS_SUBDIR
    if not chapter_dir.is_dir(): chapter_dir = Path(output_dir)
    report_text = "\n\n".join(path.read_text(encoding="utf-8") for path in sorted(chapter_dir.glob("_ch*.md")))
    payload = build_thesis_test_ledger(output_dir, list(competitive_tests or []), list(thresholds or []), list(probability_sets or []), change_reason=str(change_reason or "").strip(), freeze=False)
    result = persist_thesis_test_ledger(
        output_dir, payload, report_text=report_text,
        allow_frozen_update=bool(repair_invalid_frozen),
    )
    if result.get("written"):
        result["binding"] = bind_thesis_test_references(output_dir, result.get("ledger") or payload)
        rebound_text = "\n\n".join(path.read_text(encoding="utf-8") for path in sorted(chapter_dir.glob("_ch*.md")))
        if freeze:
            result["promotion"] = promote_reviewable_thesis_test(output_dir, report_text=rebound_text)
        result["validation"] = evaluate_output_thesis_test(output_dir, report_text=rebound_text, persist=True)
    return result


def write_decisive_question_findings(
    output_dir: str = ".",
    findings: list[dict[str, Any]] | None = None,
    resume_best_rejected: bool = False,
    finding_patches: list[dict[str, Any]] | None = None,
    change_reason: str = "",
) -> dict[str, Any]:
    """Record how research changed competing explanations and the decision."""
    try:
        from scripts.decisive_question import build_decisive_question_findings, patch_decisive_question_findings, persist_decisive_question_findings
    except ModuleNotFoundError:
        from decisive_question import build_decisive_question_findings, patch_decisive_question_findings, persist_decisive_question_findings
    submitted_findings = list(findings or [])
    submitted_patches = list(finding_patches or [])
    if resume_best_rejected and submitted_findings and submitted_patches:
        return {
            "written": False,
            "error": "ambiguous_resume_submission:use_findings_or_finding_patches_not_both",
        }
    if resume_best_rejected and submitted_patches:
        return patch_decisive_question_findings(
            output_dir, submitted_patches,
            change_reason=str(change_reason or "").strip(),
        )
    # A strict provider may still choose to resend the complete candidate while
    # setting the resume flag. Convert only actual field deltas into the bounded
    # patch path so already-valid questions cannot regress silently.
    if resume_best_rejected and submitted_findings:
        best_path = Path(output_dir) / "decisive_question_findings_best_rejected.json"
        try:
            best = json.loads(best_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"written": False, "error": "compatible_best_rejected_missing"}
        best_rows = {
            str(item.get("question_id")): item
            for item in best.get("findings") or [] if isinstance(item, dict)
        }
        submitted_rows = {
            str(item.get("question_id")): item
            for item in submitted_findings if isinstance(item, dict)
        }
        if set(best_rows) != set(submitted_rows) or len(submitted_rows) != len(submitted_findings):
            return {"written": False, "error": "full_resume_question_identity_mismatch"}
        patchable = {
            "outcome", "evidence_observation_ids", "evidence_calculation_ids",
            "attempted_sources", "signal_results", "explanation_update",
            "inference_audit", "resolution_assessment", "decision_update",
            "conclusion", "unresolved",
        }
        derived_patches: list[dict[str, Any]] = []
        for question_id, submitted in submitted_rows.items():
            delta = {"question_id": question_id}
            for key in patchable:
                if submitted.get(key) != best_rows[question_id].get(key):
                    delta[key] = submitted.get(key)
            if len(delta) > 1:
                derived_patches.append(delta)
        if not derived_patches:
            return {"written": False, "error": "full_resume_has_no_finding_deltas"}
        return patch_decisive_question_findings(
            output_dir, derived_patches,
            change_reason=str(change_reason or "").strip(),
        )
    if resume_best_rejected:
        return {"written": False, "error": "resume_submission_empty"}
    payload = build_decisive_question_findings(
        output_dir, submitted_findings, change_reason=str(change_reason or "").strip()
    )
    return persist_decisive_question_findings(output_dir, payload)


def write_insight_ledger(
    output_dir: str = ".",
    archetype: str = "",
    decisive_question: str = "",
    question_basis: dict[str, Any] | None = None,
    insights: list[dict[str, Any]] | None = None,
    reverse_expectations: dict[str, Any] | None = None,
    value_realization: dict[str, Any] | None = None,
    adversarial_review: dict[str, Any] | None = None,
    memo: dict[str, Any] | None = None,
    change_reason: str = "",
    freeze: bool = True,
    repair_invalid_frozen: bool = False,
) -> dict[str, Any]:
    """Persist the decisive question, 1-3 insights and compact memo source."""
    try:
        from scripts.insight_ledger import build_insight_ledger, persist_insight_ledger, bind_insight_references, promote_reviewable_insight, evaluate_output_insight
    except ModuleNotFoundError:
        from insight_ledger import build_insight_ledger, persist_insight_ledger, bind_insight_references, promote_reviewable_insight, evaluate_output_insight
    chapter_dir = Path(output_dir) / CHAPTERS_SUBDIR
    if not chapter_dir.is_dir(): chapter_dir = Path(output_dir)
    report_text = "\n\n".join(path.read_text(encoding="utf-8") for path in sorted(chapter_dir.glob("_ch*.md")))
    payload = build_insight_ledger(
        output_dir, archetype, decisive_question, dict(question_basis or {}),
        list(insights or []), dict(reverse_expectations or {}), dict(value_realization or {}),
        dict(adversarial_review or {}), dict(memo or {}),
        change_reason=str(change_reason or "").strip(), freeze=False,
    )
    result = persist_insight_ledger(
        output_dir, payload, report_text=report_text,
        allow_frozen_update=bool(repair_invalid_frozen),
    )
    if result.get("written"):
        result["binding"] = bind_insight_references(output_dir, payload)
        rebound_text = "\n\n".join(path.read_text(encoding="utf-8") for path in sorted(chapter_dir.glob("_ch*.md")))
        if freeze:
            result["promotion"] = promote_reviewable_insight(output_dir, report_text=rebound_text)
        result["validation"] = evaluate_output_insight(output_dir, report_text=rebound_text, persist=True)
    return result


def write_judgment_review(
    output_dir: str = ".",
    ceiling_verdict: str = "",
    verdict_basis: str = "",
    distinctive_insight: dict[str, Any] | None = None,
    competent_but_conventional: list[str] | None = None,
    fragile_leaps: list[dict[str, Any]] | None = None,
    competitive_explanation_test: dict[str, Any] | None = None,
    missing_information: list[str] | None = None,
    decision_dependency: dict[str, Any] | None = None,
    dimension_assessments: dict[str, Any] | None = None,
    reviewer_limits: list[str] | None = None,
) -> dict[str, Any]:
    """Persist an independent, diagnostic-only review of the insight ceiling."""
    try:
        from scripts.judgment_review import build_judgment_review, persist_judgment_review
    except ModuleNotFoundError:
        from judgment_review import build_judgment_review, persist_judgment_review
    payload = build_judgment_review(
        output_dir, ceiling_verdict, verdict_basis, dict(distinctive_insight or {}),
        list(competent_but_conventional or []), list(fragile_leaps or []),
        dict(competitive_explanation_test or {}), list(missing_information or []),
        dict(decision_dependency or {}), dict(dimension_assessments or {}),
        list(reviewer_limits or []),
    )
    return persist_judgment_review(output_dir, payload)


def plan_judgment_research(
    output_dir: str = ".",
    max_tasks_per_run: int = 3,
) -> dict[str, Any]:
    """Turn judgment gaps into a bounded, mutation-scoped research queue."""
    try:
        from scripts.judgment_research_router import persist_judgment_research_plan
    except ModuleNotFoundError:
        from judgment_research_router import persist_judgment_research_plan
    return persist_judgment_research_plan(
        output_dir, max_tasks_per_run=max_tasks_per_run
    )


def begin_judgment_research_task_tool(
    output_dir: str = ".",
    task_id: str = "",
) -> dict[str, Any]:
    """Activate the next queued judgment-research task."""
    try:
        from scripts.judgment_research_execution import begin_judgment_research_task
    except ModuleNotFoundError:
        from judgment_research_execution import begin_judgment_research_task
    return begin_judgment_research_task(output_dir, task_id)


def complete_judgment_research_task_tool(
    output_dir: str = ".",
    task_id: str = "",
    outcome: str = "",
    source_ids: list[str] | None = None,
    new_evidence_summary: str = "",
    finding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Complete an active task after tool/budget/mutation verification."""
    try:
        from scripts.judgment_research_execution import complete_judgment_research_task
    except ModuleNotFoundError:
        from judgment_research_execution import complete_judgment_research_task
    return complete_judgment_research_task(
        output_dir, task_id, outcome, list(source_ids or []), new_evidence_summary,
        dict(finding or {}),
    )


def finalize_judgment_research_synthesis_tool(
    output_dir: str = ".",
    integrated_task_ids: list[str] | None = None,
    verdict_change: dict[str, Any] | None = None,
    resolved_gaps: list[str] | None = None,
    remaining_gaps: list[str] | None = None,
    decision_conclusion: str = "",
) -> dict[str, Any]:
    """Finalize the independent post-research judgment synthesis."""
    try:
        from scripts.judgment_research_synthesis import finalize_judgment_research_synthesis
    except ModuleNotFoundError:
        from judgment_research_synthesis import finalize_judgment_research_synthesis
    return finalize_judgment_research_synthesis(
        output_dir,
        integrated_task_ids=list(integrated_task_ids or []),
        verdict_change=dict(verdict_change or {}),
        resolved_gaps=list(resolved_gaps or []),
        remaining_gaps=list(remaining_gaps or []),
        decision_conclusion=decision_conclusion,
    )


def finalize_judgment_research_review(
    output_dir: str = ".",
    judgment_review: dict[str, Any] | None = None,
    integrated_task_ids: list[str] | None = None,
    verdict_change: dict[str, Any] | None = None,
    resolved_gaps: list[str] | None = None,
    remaining_gaps: list[str] | None = None,
    decision_conclusion: str = "",
) -> dict[str, Any]:
    """Atomically persist the challenger review and finalize its synthesis.

    Remaining gaps are deterministically copied into ``missing_information``.
    This preserves the semantic gate while removing a brittle two-call,
    verbatim-text synchronization burden from the model.
    """
    review = dict(judgment_review or {})
    gaps = [str(item).strip() for item in (remaining_gaps or []) if str(item).strip()]
    missing = [
        str(item).strip() for item in (review.get("missing_information") or [])
        if str(item).strip()
    ]
    review["missing_information"] = list(dict.fromkeys([*missing, *gaps]))
    try:
        from scripts.judgment_review import build_judgment_review, persist_judgment_review
        from scripts.judgment_research_synthesis import finalize_judgment_research_synthesis
    except ModuleNotFoundError:
        from judgment_review import build_judgment_review, persist_judgment_review
        from judgment_research_synthesis import finalize_judgment_research_synthesis
    payload = build_judgment_review(
        output_dir,
        str(review.get("ceiling_verdict") or ""),
        str(review.get("verdict_basis") or ""),
        dict(review.get("distinctive_insight") or {}),
        list(review.get("competent_but_conventional") or []),
        list(review.get("fragile_leaps") or []),
        dict(review.get("competitive_explanation_test") or {}),
        list(review.get("missing_information") or []),
        dict(review.get("decision_dependency") or {}),
        dict(review.get("dimension_assessments") or {}),
        list(review.get("reviewer_limits") or []),
    )
    persisted = persist_judgment_review(output_dir, payload)
    if not persisted.get("written"):
        return {
            "finalized": False,
            "stage": "judgment_review",
            "errors": (
                (persisted.get("validation") or {}).get("invalid_findings", [])
                + (persisted.get("validation") or {}).get("incomplete_findings", [])
            ),
            "review": persisted,
        }
    finalized = finalize_judgment_research_synthesis(
        output_dir,
        integrated_task_ids=list(integrated_task_ids or []),
        verdict_change=dict(verdict_change or {}),
        resolved_gaps=list(resolved_gaps or []),
        remaining_gaps=gaps,
        decision_conclusion=decision_conclusion,
    )
    finalized["review_written"] = True
    finalized["atomic"] = True
    return finalized


def record_research_outcomes(
    output_dir: str = ".",
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Append outcomes; Phase 06 plans require the strict source-hashed contract."""
    if Path(output_dir, "monitoring_plan.json").is_file():
        try:
            from scripts.research_monitoring import append_monitoring_events
        except ModuleNotFoundError:
            from research_monitoring import append_monitoring_events
        return append_monitoring_events(output_dir, list(events or []))
    try:
        from scripts.research_calibration import record_monitoring_outcomes
    except ModuleNotFoundError:
        from research_calibration import record_monitoring_outcomes
    return record_monitoring_outcomes(output_dir, list(events or []))


def append_strict_monitoring_events(
    output_dir: str = ".",
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Append source-hashed post-publication events under the Phase 06 contract."""
    try:
        from scripts.research_monitoring import append_monitoring_events
    except ModuleNotFoundError:
        from research_monitoring import append_monitoring_events
    return append_monitoring_events(output_dir, list(events or []))


def _decision_from_section(text: str, heading: str, values: tuple[str, ...]) -> str:
    match = re.search(rf"^###\s+{re.escape(heading)}.*?$([\s\S]*?)(?=^###\s+|\Z)", text, re.MULTILINE)
    haystack = match.group(1) if match else text
    for value in values:
        if re.search(rf"\b{re.escape(value)}\b", haystack, re.IGNORECASE):
            return value.lower()
    return ""


def _infer_and_write_decision_manifest(output_dir: str) -> dict[str, Any] | None:
    """Legacy bridge: infer structured decision from Ch14 once, then persist it."""
    ch14_path = os.path.join(output_dir, CHAPTERS_SUBDIR, "_ch14.md")
    if not os.path.exists(ch14_path):
        ch14_path = os.path.join(output_dir, "_ch14.md")
    try:
        text = Path(ch14_path).read_text(encoding="utf-8")
    except OSError:
        return None
    qual = _decision_from_section(text, "定性研究决定", ("Continue", "Pause", "Abandon"))
    quant = _decision_from_section(text, "定量投资决定", ("Buy", "Hold", "Avoid"))
    if not qual or not quant:
        return None
    pos_match = re.search(r"(?:建议仓位|观察仓|仓位)[^\n%]{0,40}?(\d+(?:\.\d+)?)\s*%", text)
    return write_decision_manifest(
        output_dir=output_dir,
        qualitative_decision=qual,
        quantitative_decision=quant,
        position_pct=float(pos_match.group(1)) if pos_match else 0.0,
    )


def _check_dividend_identity(report_text: str, compute_bundle: dict[str, Any]) -> dict[str, Any]:
    """Compare current-yield claims with the currency-normalized canonical identity."""
    factor4 = compute_bundle.get("factor4", {}) if isinstance(compute_bundle, dict) else {}
    identity = factor4.get("dividend_identity", {}) if isinstance(factor4, dict) else {}
    expected = identity.get("yield_pretax_pct") or factor4.get("dps_yield_pretax")
    try:
        expected_value = float(expected)
    except (TypeError, ValueError):
        return {"status": "SKIP", "expected_yield_pct": None, "contradictions": []}
    try:
        expected_after_tax = float(
            identity.get("yield_after_tax_pct") or factor4.get("dps_yield_after_tax")
        )
    except (TypeError, ValueError):
        expected_after_tax = None

    excluded_context = re.compile(
        r"同行|行业|可比|百分位|第三方|历史|过去|情景|敏感|压力|假设|"
        r"若|下降到|降至|升至|提高到|特别股息|含特别|peer|P\d+(?:\.\d+)?|"
        r"存款利率|governance|未知来源"
    )
    contradictions: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(?:当前|最新|本期|常规|税前|税后|预期)?\s*股息率\s*"
        r"(?:为|约|≈|=|：|:)?\s*(\d+(?:\.\d+)?)\s*%"
    )
    current_chapter = 0
    for line_no, line in enumerate(report_text.splitlines(), 1):
        heading = re.match(r"^##\s+Ch(\d+)\b", line)
        if heading:
            current_chapter = int(heading.group(1))
        if excluded_context.search(line):
            continue
        for match in pattern.finditer(line):
            component_context = line[max(0, match.start() - 36):match.end() + 8]
            if re.search(
                r"常规(?:DPS|股息率)|中期(?:DPS|股息率)|特别(?:DPS|股息率)|"
                r"分项股息率|component",
                component_context,
                re.IGNORECASE,
            ):
                continue
            # “税后股息率6.91%” uses the after-tax identity; when a line says
            # “股息率7.68%税前（6.91%税后）”, the matched primary claim is pretax.
            tax_context_before_claim = line[max(0, match.start() - 8):match.end()]
            line_expected = (
                expected_after_tax
                if "税后" in tax_context_before_claim and expected_after_tax is not None
                else expected_value
            )
            reported = float(match.group(1))
            if abs(reported - line_expected) > 0.75:
                contradictions.append({
                    "line": line_no,
                    "chapter": current_chapter,
                    "reported_yield_pct": reported,
                    "expected_yield_pct": line_expected,
                    "text": line.strip()[:240],
                })
    return {
        "status": "FAIL" if contradictions else "PASS",
        "expected_yield_pct": expected_value,
        "expected_after_tax_yield_pct": expected_after_tax,
        "currency": identity.get("price_currency"),
        "period": identity.get("period"),
        "contradictions": contradictions,
    }


def _audit_ledger_path(output_dir: str) -> str:
    return os.path.join(output_dir, "chapter_audit_ledger.json")


def _persist_chapter_audit(
    output_dir: str,
    chapter_index: int,
    title: str,
    audit: dict[str, Any],
    *,
    attempt: int,
    char_count: int,
) -> None:
    """Persist every audit attempt so completion checks use run evidence, not prompt claims."""
    ledger_path = _audit_ledger_path(output_dir)
    ledger: dict[str, Any] = {"schema_version": "chapter-audit.v1", "chapters": {}}
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path, encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                ledger.update(loaded)
        except (OSError, json.JSONDecodeError):
            pass
    chapters = ledger.setdefault("chapters", {})
    key = str(int(chapter_index))
    chapter = chapters.setdefault(key, {"index": int(chapter_index), "title": title, "attempts": []})
    chapter["title"] = title or chapter.get("title", "")
    record = {
        "attempt": int(attempt),
        "char_count": int(char_count),
        "passed": bool(audit.get("passed", False)),
        "verdict": str(audit.get("verdict", "fail")),
        "error_count": int(audit.get("error_count", 0)),
        "warn_count": int(audit.get("warn_count", 0)),
        "violations": list(audit.get("violations", [])),
    }
    chapter.setdefault("attempts", []).append(record)
    chapter["final"] = record
    tmp_path = ledger_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(ledger, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, ledger_path)


def _enforce_depth_contract(
    audit: dict[str, Any],
    content: str,
    chapter_index: int,
    output_dir: str,
) -> dict[str, Any]:
    """Overlay the output-specific semantic-depth profile on the base audit."""
    depth = analyze_chapter_depth(
        content,
        chapter_index,
        data_rich=detect_data_richness(output_dir),
    )
    if depth["status"] == "PASS":
        return depth
    if not any(item.get("rule") == "P2_RICH_DEPTH" for item in audit.get("violations", [])):
        description = "实质深度不足：" + depth_failure_description(depth)
        audit.setdefault("violations", []).append({
            "rule": "P2_RICH_DEPTH",
            "severity": "error",
            "desc": description,
        })
        audit["error_count"] = int(audit.get("error_count", 0)) + 1
        audit["passed"] = False
        audit["verdict"] = "fail"
        repair_line = "补足当前数据档的语义深度：" + depth_failure_description(depth)
        repair = audit.get("repair_plan")
        if isinstance(repair, list):
            repair.append(repair_line)
        elif isinstance(repair, str) and repair:
            audit["repair_plan"] = repair + "\n" + repair_line
        else:
            audit["repair_plan"] = repair_line
    return depth


def write_chapter(
    output_dir: str = ".",
    chapter_index: int = 0,
    title: str = "",
    content: str = "",
    force_rewrite: bool = False,
) -> dict[str, Any]:
    """写入单章内容到文件。

    自动运行可编程审计（S1占位符 / E1证据密度 / C2禁止项），
    将审计结果附带在返回值中。

    Args:
        output_dir: 股票输出目录。
        chapter_index: 章序号（V13 为 0-14）。
        title: 章节标题。
        content: 章节 Markdown 内容。

    Returns:
        ``{path, char_count, audit: {violations}}``。
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"_ch{int(chapter_index):02d}.md"
    chapters_d = os.path.join(output_dir, CHAPTERS_SUBDIR)
    os.makedirs(chapters_d, exist_ok=True)
    path = os.path.join(chapters_d, filename)

    # 幂等守卫只保护真正通过当前审计的章节；质量修复可显式强制重写。
    if os.path.exists(path) and not force_rewrite:
        try:
            with open(path, encoding="utf-8") as _f:
                _existing = _f.read()
            canonical_heading = rf"^##\s+Ch{int(chapter_index)}\b"
            if len(_existing) >= 800 and re.search(canonical_heading, _existing, re.MULTILINE):
                _quick_audit = _audit_content(_existing, chapter_index=chapter_index)
                _existing_depth = _enforce_depth_contract(
                    _quick_audit, _existing, chapter_index, output_dir
                )
                _enforce_graham_block(_quick_audit, _existing, chapter_index)
                _enforce_av_bridge(_quick_audit, _existing, chapter_index)
                _enforce_av_method(_quick_audit, _existing, chapter_index)
                _enforce_reliability_language(
                    _quick_audit, _existing, chapter_index, output_dir
                )
                if _quick_audit.get("passed") and _quick_audit.get("error_count", 0) == 0:
                    # 即使跳过内容重写，也要留下本轮可验证的审计记录，避免
                    # completion contract 因 missing_audit_record 永久阻断。
                    _persist_chapter_audit(
                        output_dir,
                        chapter_index,
                        title,
                        _quick_audit,
                        attempt=0,
                        char_count=len(_existing),
                    )
                    return {
                        "path": path,
                        "chapter_index": chapter_index,
                        "title": title,
                        "char_count": len(_existing),
                        "audit": _quick_audit,
                        "depth": _existing_depth,
                        "skipped": True,
                        "reason": (
                            f"_ch{int(chapter_index):02d}.md 已存在（{len(_existing)} 字符）且审计通过"
                            f"（error_count=0）—— 跳过重写。"
                            f"如需深化或修复，请以 force_rewrite=true 重新写入。"
                        ),
                    }
        except OSError:
            pass  # 读取失败 → 回落到正常写入

    content = _ensure_canonical_chapter_heading(content, chapter_index)
    # Phase 04: compiler-owned decision blocks are immutable from the
    # chapter-writing surface.  Agents may improve the surrounding reasoning,
    # but cannot silently delete or rewrite canonical values/actions.
    if os.path.exists(path):
        try:
            from scripts.decision_compiler import preserve_protected_blocks
        except ModuleNotFoundError:
            from decision_compiler import preserve_protected_blocks
        try:
            with open(path, encoding="utf-8") as _f:
                content = preserve_protected_blocks(
                    _f.read(), content, int(chapter_index)
                )
        except OSError:
            pass

    # 长度守卫：追踪本次为第几次尝试（仅用于生成反馈信息，不阻止写盘）
    _write_attempt_counts[path] = _write_attempt_counts.get(path, 0) + 1
    _attempt_num = _write_attempt_counts[path]

    # 与 audit_rules/report_completion 共用语义深度契约；换行排版不影响判定。
    _short_feedback = None
    if content:
        _depth = analyze_chapter_depth(
            content,
            chapter_index,
            data_rich=detect_data_richness(output_dir),
        )
        if _depth["status"] == "FAIL":
            _short_feedback = (
                f"实质深度不足（第 {_attempt_num} 次）：{depth_failure_description(_depth)}。"
                "文件仅作为草稿写入，正式报告仍被阻断；请补充可核查数字、"
                "多年趋势、因果判断和公式/情景推导，不要通过逐句换行凑长度。"
            )

    # 始终写盘：即使过短也先落盘，确保章节文件永不缺失（assemble 不校验完整性）
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    # 自动审计
    audit = _audit_content(content, chapter_index=chapter_index)
    _depth = _enforce_depth_contract(audit, content, chapter_index, output_dir)
    _enforce_graham_block(audit, content, chapter_index)
    _enforce_av_bridge(audit, content, chapter_index)
    _enforce_av_method(audit, content, chapter_index)
    _enforce_reliability_language(audit, content, chapter_index, output_dir)
    _persist_chapter_audit(
        output_dir,
        chapter_index,
        title,
        audit,
        attempt=_attempt_num,
        char_count=len(content),
    )

    _ret = {
        "path": path,
        "chapter_index": chapter_index,
        "title": title,
        "char_count": len(content),
        "depth": _depth,
        "audit": audit,
    }
    try:
        from scripts.decision_compiler import validate_chapter_decision_bindings
    except ModuleNotFoundError:
        from decision_compiler import validate_chapter_decision_bindings
    binding_validation = validate_chapter_decision_bindings(
        output_dir, int(chapter_index)
    )
    _ret["decision_binding_validation"] = binding_validation
    if binding_validation.get("state") == "INVALID":
        _ret["passed"] = False
        _ret["error"] = (
            "章节含未绑定或错误绑定的canonical关键值："
            + "; ".join(binding_validation.get("invalid_findings") or [])
        )
    # 过短反馈：文件已落盘，但提示 Agent 重写加长（short_content 不计入死循环真实写入数）
    if _short_feedback is not None:
        _ret["short_content"] = True
        _ret["passed"] = False
        _ret["error"] = _short_feedback
        _ret["attempt"] = _attempt_num
    return _ret


def read_chapter(
    output_dir: str = ".",
    chapter_index: int = 0,
) -> dict[str, Any]:
    """读取已写入的章节内容。

    Args:
        output_dir: 股票输出目录。
        chapter_index: 章序号（V13 为 0-14）。

    Returns:
        ``{chapter_index, title, content, char_count}``。
    """
    filename = f"_ch{int(chapter_index):02d}.md"
    # v13+: chapters live in chapters/ subdir; fallback to root for legacy v12 dirs
    chapters_d = os.path.join(output_dir, CHAPTERS_SUBDIR)
    if os.path.exists(os.path.join(chapters_d, filename)):
        path = os.path.join(chapters_d, filename)
    else:
        path = os.path.join(output_dir, filename)

    if not os.path.exists(path):
        return {"chapter_index": chapter_index, "error": f"章节 {filename} 不存在", "content": ""}

    with open(path, encoding="utf-8") as f:
        content = f.read()

    # 提取标题（匹配 # 或 ## 开头）
    title = ""
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            break
        elif stripped.startswith("## "):
            title = stripped[3:].strip()
            if not title:
                continue
            break

    return {
        "chapter_index": chapter_index,
        "title": title,
        "content": content,
        "char_count": len(content),
    }


def _extract_sources(report_text: str, output_dir: str, source_json_name: str = "_sources.json") -> str:
    """Extract anchors into canonical structured JSON and Markdown footnotes."""
    import json as _json, re as _re
    sources: list[dict] = []
    seen: dict[str, int] = {}
    try:
        from scripts.evidence_citation import EvidenceRegistry
    except ModuleNotFoundError:
        from evidence_citation import EvidenceRegistry
    registry = EvidenceRegistry()
    registry.register_from_output_dir(output_dir)

    def _repl(m):
        raw = m.group(1).strip()
        # 去重
        if raw in seen:
            return f"[^{seen[raw]}]"
        idx = len(sources) + 1
        seen[raw] = idx
        canonical, unresolved = registry.canonicalize_anchor(raw)
        display_sources = canonical or unresolved or [raw]
        sources.append({
            "id": idx,
            "raw_anchor": raw,
            "canonical_sources": canonical,
            # Legacy consumers expect file/claim; keep them with corrected identity.
            "file": "; ".join(display_sources),
            "claim": raw,
        })
        return f"[^{idx}]"

    text = _re.sub(r'\[(?:table-)?source:\s*([^\]]+)\]', _repl, report_text, flags=_re.IGNORECASE)

    # 生成脚注
    footnotes = "\n\n---\n\n"
    for s in sources:
        footnotes += f"[^{s['id']}]: `{s['file']}` — {s['claim']}\n"

    # 保存 JSON
    json_path = os.path.join(output_dir, source_json_name)
    with open(json_path, "w", encoding="utf-8") as f:
        _json.dump(sources, f, indent=2, ensure_ascii=False)

    return text + footnotes


def assemble_report(
    output_dir: str = ".",
    company_name: str = "",
    ts_code: str = "",
    validation_only: bool = False,
) -> dict[str, Any]:
    """组装最终报告。

    拼接所有已写章节，添加来源清单，写入完整报告文件。

    Args:
        output_dir: 股票输出目录。
        company_name: 公司全称。
        ts_code: 股票代码。

    Returns:
        ``{path, chapter_count, char_count}``。
    """
    # The unified report context stores the issuer under ``meta.issuer``.
    # Validation-only resume runs may not rebuild AgentLoop's transient
    # ``company_name`` field, so recover the stable identity before rendering
    # either the memo or the technical report.  A blank report title is never
    # an acceptable representation of a valid company identity.
    company_name = str(company_name or "").strip()
    if not company_name:
        for identity_file in ("report_context.json", "analysis_contract.json"):
            try:
                identity = json.loads((Path(output_dir) / identity_file).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            meta = identity.get("meta") if isinstance(identity.get("meta"), dict) else {}
            candidate = identity.get("company_name") or meta.get("issuer")
            if isinstance(candidate, str) and candidate.strip():
                company_name = candidate.strip()
                break
    if not company_name:
        company_name = ts_code

    # Phase 04: canonical values/actions are compiled immediately before any
    # chapter bytes are read.  Legacy directories without an enforcement
    # policy remain unchanged; new unified runs cannot publish free-form
    # decision sections.
    try:
        from scripts.decision_compiler import compile_decision_sections
    except ModuleNotFoundError:
        from decision_compiler import compile_decision_sections
    compiler_policy = Path(output_dir) / "decision_compiler_policy.json"
    compiler_result: dict[str, Any] = {"state": "SKIP", "written": False}
    if compiler_policy.is_file():
        compiler_result = compile_decision_sections(output_dir, persist=True)

    # v13+: chapters live in chapters/ subdir; fallback to root for legacy v12 dirs
    chapters_d = os.path.join(output_dir, CHAPTERS_SUBDIR)
    if os.path.isdir(chapters_d) and any(
        f.startswith("_ch") and f.endswith(".md") for f in os.listdir(chapters_d)
    ):
        _ch_dir = chapters_d
    else:
        _ch_dir = output_dir
    chapter_files = sorted(
        f for f in os.listdir(_ch_dir)
        if f.startswith("_ch") and f.endswith(".md")
    )

    header_parts: list[str] = [
        f"# {company_name} ({ts_code}) 龟龟策略分析报告",
        "",
        f"> 由 TurtleAgent V12 单 Agent 工具循环生成 | Dayu定性+Turtle定量 | {len(chapter_files)} 章",
        f"> 分析日期: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}",
        "",
        "**风险警示与免责声明**：*本文由AI/大模型基于公开披露且可核查的财报/公告文件辅助生成，仅用于学术研究与信息交流之目的。阅读后产生的任何观点需核对原文。*",
        "",
    ]

    body_parts: list[str] = []
    for cf in chapter_files:
        path = os.path.join(_ch_dir, cf)
        with open(path, encoding="utf-8") as f:
            body_parts.append(f.read().strip())

    # 组装正文（不含来源清单）→ 提取来源 → 追加来源清单
    body_text = "\n\n---\n\n".join(body_parts)
    # 只整理最终展示文本，不改章节真相源；保守合并同一小节内的短单句段落。
    try:
        from scripts.report_prose import normalize_markdown_paragraphs
    except ModuleNotFoundError:
        from report_prose import normalize_markdown_paragraphs
    body_text = normalize_markdown_paragraphs(body_text)
    temp_text = "\n".join(header_parts) + body_text

    # 新报告应由 Agent 显式调用 write_decision_manifest；现有存量章节允许
    # 一次性从 Ch14 推断并落盘，之后完成契约会验证 Ch0/Ch14/manifest 一致。
    decision_manifest_path = os.path.join(output_dir, "decision_manifest.json")
    if not os.path.exists(decision_manifest_path):
        _infer_and_write_decision_manifest(output_dir)

    # V12: 来源清单 — 从各章证据与出处聚合，去重
    try:
        from scripts.source_list_builder import build_source_list
    except ModuleNotFoundError:
        from source_list_builder import build_source_list
    try:
        from scripts.evidence_citation import EvidenceRegistry as _EvidenceRegistry
    except ModuleNotFoundError:
        from evidence_citation import EvidenceRegistry as _EvidenceRegistry
    source_registry = _EvidenceRegistry()
    source_registry.register_from_output_dir(output_dir)
    source_section = build_source_list(temp_text, source_registry)
    if not source_section.strip() or len(source_section.strip()) < 50:
        # Fallback: 扫描各章 [source: ...] 引用，按来源文件去重合并
        import re as _re
        file_entries = {}  # {filename: set of claims}
        for cf in chapter_files:
            path = os.path.join(_ch_dir, cf)
            with open(path, encoding="utf-8") as f:
                text = f.read()
                for m in _re.finditer(r'\[(?:table-)?source:\s*([^\]]+)\]', text, _re.IGNORECASE):
                    raw = m.group(1).strip()
                    # 去掉模板占位符和格式残片
                    _PLACEHOLDERS = {"来源名 具体数值", "文件名", "文件名 → 字段 = 值", "来源名",
                                    "...", "X", "x", "-", "--", "... | ... | ...", "|"}
                    if raw in _PLACEHOLDERS or len(raw) <= 1:
                        continue
                    if all(c in ".|-_… Xx" for c in raw):  # 纯格式字符
                        continue
                    # 提取文件名（第一个词）和数据描述（剩余部分）
                    parts = raw.split(None, 1)
                    fname = parts[0] if parts else raw
                    detail = parts[1] if len(parts) > 1 else ""
                    if fname not in file_entries:
                        file_entries[fname] = set()
                    if detail:
                        file_entries[fname].add(detail)
        if file_entries:
            lines = ["## 来源清单", ""]
            for fname in sorted(file_entries.keys()):
                details = file_entries[fname]
                if len(details) <= 2:
                    for d in sorted(details):
                        lines.append(f"- `{fname}` — {d}")
                else:
                    lines.append(f"- `{fname}` ({len(details)}处引用)")
            lines.append(f"\n_共 {sum(len(v) for v in file_entries.values())} 个来源引用，{len(file_entries)} 个文件_")
            source_section = "\n".join(lines)
        else:
            source_section = "## 来源清单\n\n各章「证据与出处」小节已列出详细来源。"

    technical_appendix_path = os.path.join(output_dir, "_technical_appendix.md")
    technical_appendix = ""
    if os.path.exists(technical_appendix_path):
        with open(technical_appendix_path, encoding="utf-8") as f:
            technical_appendix = f.read().strip()

    report_parts = ["\n".join(header_parts), body_text]
    if technical_appendix:
        report_parts.append(technical_appendix)
    if source_section:
        report_parts.append(source_section)
    report_text = "\n\n---\n\n".join(part for part in report_parts if part and part.strip())

    try:
        from scripts.report_completion import evaluate_report_completion
    except ModuleNotFoundError:
        from report_completion import evaluate_report_completion

    completion = evaluate_report_completion(report_text, output_dir)
    reports_d = os.path.join(output_dir, REPORTS_SUBDIR)
    os.makedirs(reports_d, exist_ok=True)
    code_short = ts_code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")

    if completion.status not in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}:
        drafts_d = os.path.join(reports_d, 'drafts')
        os.makedirs(drafts_d, exist_ok=True)
        report_path = os.path.join(drafts_d, f"{code_short}_分析报告_{REPORT_VERSION}_draft.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        return {
            "path": report_path,
            "tool_name": "assemble_report",
            "chapter_count": len(chapter_files),
            "char_count": len(report_text),
            "completion": completion.to_dict(),
            "decision_compiler": compiler_result,
            "published": False,
            "error": "报告未通过完成契约，已保留 draft，禁止发布正式报告",
        }

    # V12: 质量门必须先于正式文件写入；过去这里先发布再审计，导致
    # enhanced_quality_gate=BLOCKED 时仍出现伪 COMPLETE 正式报告。
    quality_result = _run_quality_checks(report_text, output_dir)
    completion_dict = completion.to_dict()
    completion_dict['validators']['quality'] = quality_result
    if not quality_result.get("passed", False):
        completion_dict["status"] = "BLOCKED"
        quality_issues = list(quality_result.get("issues", [])) or ["quality_gate_failed"]
        completion_dict["blocking_findings"].extend(
            f"Quality: {issue}" for issue in quality_issues
        )
        Path(os.path.join(output_dir, "completion_report.json")).write_text(
            json.dumps(completion_dict, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        drafts_d = os.path.join(reports_d, 'drafts')
        os.makedirs(drafts_d, exist_ok=True)
        report_path = os.path.join(drafts_d, f"{code_short}_分析报告_{REPORT_VERSION}_draft.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        return {
            "path": report_path,
            "tool_name": "assemble_report",
            "chapter_count": len(chapter_files),
            "char_count": len(report_text),
            "quality": quality_result,
            "completion": completion_dict,
            "published": False,
            "error": "增强质量门未通过，已保留 draft，禁止发布正式报告",
        }

    validation_report_text = report_text
    insight_policy_path = Path(output_dir) / "insight_policy.json"
    try:
        insight_policy = json.loads(insight_policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        insight_policy = {}
    dual_layer = bool(insight_policy.get("enforced"))
    technical_filename = (
        f"{code_short}_分析报告_{REPORT_VERSION}_technical_draft.md"
        if validation_only else f"{code_short}_分析报告_{REPORT_VERSION}_technical.md"
    )
    technical_report_text = _extract_sources(report_text, output_dir, "_technical_sources.json") if dual_layer else ""
    memo_preservation = None
    if dual_layer:
        try:
            from scripts.insight_ledger import render_investment_memo, validate_rendered_memo
        except ModuleNotFoundError:
            from insight_ledger import render_investment_memo, validate_rendered_memo
        try:
            insight_payload = json.loads((Path(output_dir) / "insight_ledger.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            insight_payload = {}
        memo_text = render_investment_memo(insight_payload, company_name, ts_code, technical_filename)
        memo_preservation = validate_rendered_memo(insight_payload, memo_text, technical_filename)
        Path(output_dir, "memo_preservation_report.json").write_text(
            json.dumps(memo_preservation, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        completion_dict["validators"]["memo_preservation"] = memo_preservation
        if memo_preservation.get("status") != "PASS":
            completion_dict["status"] = "BLOCKED"
            completion_dict["blocking_findings"].extend(
                f"Memo preservation: {item}" for item in memo_preservation.get("missing_fields", [])
            )
            Path(output_dir, "completion_report.json").write_text(
                json.dumps(completion_dict, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            drafts_d = os.path.join(reports_d, "drafts")
            os.makedirs(drafts_d, exist_ok=True)
            report_path = os.path.join(drafts_d, f"{code_short}_分析报告_{REPORT_VERSION}_draft.md")
            Path(report_path).write_text(memo_text, encoding="utf-8")
            return {
                "path": report_path, "tool_name": "assemble_report",
                "chapter_count": len(chapter_files), "char_count": len(memo_text),
                "quality": quality_result, "completion": completion_dict,
                "memo_preservation": memo_preservation, "published": False,
                "error": "精简报告丢失决策内容，已阻断发布",
            }
        disclaimer = "\n\n**风险警示与免责声明**：本文由AI基于公开披露辅助生成，仅供研究；投资者必须核对原始文件并独立判断。\n"
        report_text = _extract_sources(memo_text + disclaimer, output_dir)
    else:
        report_text = _extract_sources(report_text, output_dir)

    # Re-run the semantic reader contract on the actual publication text.  In
    # the dual-layer path this is the compact memo, not the full technical
    # appendix; checking only the pre-memo chapters would allow a short memo to
    # displace the reader-facing explanation while every numeric gate passed.
    try:
        from scripts.reader_coverage import evaluate_reader_coverage
    except ModuleNotFoundError:
        from reader_coverage import evaluate_reader_coverage
    reader_coverage = evaluate_reader_coverage(
        report_text,
        output_dir,
        enforced=Path(output_dir, "company_archetype.json").is_file(),
        persist=Path(output_dir, "company_archetype.json").is_file(),
    )
    completion_dict["validators"]["reader_coverage"] = reader_coverage
    if reader_coverage.get("status") == "BLOCKED":
        completion_dict["status"] = "BLOCKED"
        completion_dict["blocking_findings"].extend(
            f"Reader coverage: {item}"
            for item in reader_coverage.get("blocking_findings", [])
        )
        Path(os.path.join(output_dir, "completion_report.json")).write_text(
            json.dumps(completion_dict, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        drafts_d = os.path.join(reports_d, "drafts")
        os.makedirs(drafts_d, exist_ok=True)
        report_path = os.path.join(
            drafts_d, f"{code_short}_分析报告_{REPORT_VERSION}_draft.md"
        )
        Path(report_path).write_text(report_text, encoding="utf-8")
        return {
            "path": report_path,
            "tool_name": "assemble_report",
            "chapter_count": len(chapter_files),
            "char_count": len(report_text),
            "quality": quality_result,
            "completion": completion_dict,
            "memo_preservation": memo_preservation,
            "reader_coverage": reader_coverage,
            "published": False,
            "error": "读者层语义覆盖不足，已保留 draft，禁止发布正式报告",
        }

    # The sole formal-publication exit freezes the report, structured ledgers,
    # predictions, triggers and all resolvable source files visible at release.
    # A later changed report/ledger cannot silently overwrite this snapshot.
    try:
        from scripts.research_calibration import create_publication_snapshot
    except ModuleNotFoundError:
        from research_calibration import create_publication_snapshot
    publication_snapshot = create_publication_snapshot(
        output_dir,
        report_text,
        validation_report_text=validation_report_text,
        completion=completion_dict,
        dry_run=validation_only,
    )
    completion_dict['validators']['publication_snapshot'] = publication_snapshot
    if not publication_snapshot.get('written', False):
        completion_dict['status'] = 'BLOCKED'
        completion_dict['blocking_findings'].append(
            'Publication snapshot: ' + str(publication_snapshot.get('error') or 'snapshot_failed')
        )
        Path(os.path.join(output_dir, "completion_report.json")).write_text(
            json.dumps(completion_dict, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        drafts_d = os.path.join(reports_d, 'drafts')
        os.makedirs(drafts_d, exist_ok=True)
        report_path = os.path.join(drafts_d, f"{code_short}_分析报告_{REPORT_VERSION}_draft.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        return {
            "path": report_path, "tool_name": "assemble_report",
            "chapter_count": len(chapter_files), "char_count": len(report_text),
            "quality": quality_result, "completion": completion_dict,
            "publication_snapshot": publication_snapshot, "published": False,
            "error": "发布快照创建失败，已保留 draft，禁止覆盖正式报告",
        }
    Path(os.path.join(output_dir, "completion_report.json")).write_text(
        json.dumps(completion_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if validation_only:
        drafts_d = os.path.join(reports_d, "drafts")
        os.makedirs(drafts_d, exist_ok=True)
        report_path = os.path.join(drafts_d, f"{code_short}_分析报告_{REPORT_VERSION}_draft.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        technical_report_path = None
        if dual_layer:
            technical_report_path = os.path.join(drafts_d, technical_filename)
            with open(technical_report_path, "w", encoding="utf-8") as f:
                f.write(technical_report_text)
        return {
            "path": report_path,
            "technical_report_path": technical_report_path,
            "tool_name": "assemble_report",
            "chapter_count": len(chapter_files),
            "char_count": len(report_text),
            "quality": quality_result,
            "completion": completion_dict,
            "memo_preservation": memo_preservation,
            "publication_snapshot": publication_snapshot,
            "published": False,
            "validated": True,
        }
    report_path = os.path.join(reports_d, f"{code_short}_分析报告_{REPORT_VERSION}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    technical_report_path = None
    if dual_layer:
        technical_report_path = os.path.join(reports_d, technical_filename)
        with open(technical_report_path, "w", encoding="utf-8") as f:
            f.write(technical_report_text)

    # 同步生成 HTML（供仪表盘/web app 渲染）。失败不阻断组装——md 是真相源。
    html_path = _render_report_html(report_path)

    return {
        "path": report_path,
        "tool_name": "assemble_report",
        "html_path": html_path,
        "technical_report_path": technical_report_path,
        "chapter_count": len(chapter_files),
        "char_count": len(report_text),
        "quality": quality_result,
        "completion": completion_dict,
        "memo_preservation": memo_preservation,
        "publication_snapshot": publication_snapshot,
        "published": True,
    }


def _render_report_html(report_path: str) -> str | None:
    """把最终 md 报告渲染为同名 .html（内嵌 CSS，pandoc 缺失时降级 simple 转换）。

    复用 scripts/render_report.py 的 render_to_html。任何异常都吞掉并返回 None，
    保证报告组装不因渲染问题失败。
    """
    try:
        scripts_dir = str(Path(__file__).resolve().parents[2])
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from render_report import render_to_html

        return render_to_html(report_path)
    except Exception as exc:  # noqa: BLE001 — 渲染失败不应中断组装
        print(f"[assemble_report] HTML 渲染跳过：{exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# 审计
# ---------------------------------------------------------------------------


def audit_chapter(
    output_dir: str = ".",
    chapter_index: int = 0,
) -> dict[str, Any]:
    """审计指定章节（S1/E1/C1/C2/S2）。

    读入章节文件，运行可编程审计规则，返回违规列表。

    Args:
        output_dir: 股票输出目录。
        chapter_index: 章序号。

    Returns:
        ``{violations: [...], passed: bool}``。
    """
    filename = f"_ch{int(chapter_index):02d}.md"
    # 优先在 chapters/ 子目录查找（write_chapter 写入子目录）
    _chapters_dir = os.path.join(output_dir, CHAPTERS_SUBDIR)
    if os.path.isdir(_chapters_dir):
        path = os.path.join(_chapters_dir, filename)
    else:
        path = os.path.join(output_dir, filename)

    if not os.path.exists(path):
        return {"violations": [{"rule": "NONE", "desc": "章节不存在"}], "passed": False}

    with open(path, encoding="utf-8") as f:
        content = f.read()

    audit = _audit_content(content, chapter_index=chapter_index)
    depth = _enforce_depth_contract(audit, content, chapter_index, output_dir)
    _enforce_graham_block(audit, content, chapter_index)
    _enforce_av_bridge(audit, content, chapter_index)
    _enforce_av_method(audit, content, chapter_index)
    _enforce_reliability_language(audit, content, chapter_index, output_dir)
    audit["path"] = path
    audit["chapter_index"] = chapter_index
    audit["depth"] = depth
    return audit


# 综合派 V_final 估值块的强制标记（Ch12 DDM 章必须包含）。
# 缺失即判 fail，逼 resume 模式补写——否则批量刷新存量报告不会走新框架。
_GRAHAM_BLOCK_MARKERS = ["V_final", "V_cash", "回报安全边际"]
# 只有 canonical 框架文档存在时才强制（与 agent_loop 优雅降级一致）：
# 若框架被移除，agent 无从产出该块，此时不强制以免 resume 无限重写。
_GRAHAM_LITE_DOC = (
    Path(__file__).resolve().parents[3] / "prompts" / "references" / "_graham_framework_lite.md"
)


def _enforce_reliability_language(
    audit: dict[str, Any], content: str, chapter_index: int, output_dir: str
) -> None:
    """Fail chapter writes that contradict the structured reliability ledger."""
    if int(chapter_index) not in {11, 12, 13, 14, 0}:
        return
    try:
        valuation = json.loads(
            Path(output_dir, "valuation_model.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return
    findings: list[str] = []
    comparisons = valuation.get("model_comparisons") or []
    noncomparable_ids = {
        str(item.get("model_id") or "")
        for item in comparisons if isinstance(item, dict) and item.get("comparable") is False
    }
    aliases = {
        "M:DDM:v1": "DDM", "M:NAV:v1": "NAV",
        "M:DCF_FCFE:v1": "(?:DCF[_ -]?FCFE|FCFE)",
    }
    for model_id in sorted(noncomparable_ids):
        token = aliases.get(model_id, re.escape(model_id))
        overstates = False
        for sentence in re.split(r"[。！？!?;；\n]+", content):
            if not re.search(rf"(?:{re.escape(model_id)}|{token})", sentence, re.I):
                continue
            claim = re.search(r"交叉验证|相互印证|corroborat", sentence, re.I)
            if not claim:
                continue
            prefix = sentence[max(0, claim.start() - 18):claim.start()]
            if re.search(r"不(?:可|能|构成|是)?|禁止|并非|不得|never|not|cannot", prefix, re.I):
                continue
            overstates = True
            break
        if overstates:
            findings.append(
                f"{model_id} 已标为不可直接比较，只能称诊断/情景参考，禁止称交叉验证或相互印证"
            )
    bridge = valuation.get("cash_access_bridge") or {}
    reserve = bridge.get("parent_distributable_reserves") or {}
    verified_parent_reserve = False
    try:
        observations = json.loads(
            Path(output_dir, "fact_observations.json").read_text(encoding="utf-8")
        )
        verified_parent_reserve = any(
            isinstance(item, dict)
            and item.get("fact_name") == "parent_distributable_reserves_rmb_m"
            and str(item.get("status") or "").upper() == "VERIFIED"
            for item in observations.get("observations") or []
        )
    except (OSError, json.JSONDecodeError):
        pass
    if not verified_parent_reserve and str(reserve.get("status") or "").upper() in {
        "NOT_DISCLOSED", "UNVERIFIED", "UNKNOWN", "NOT_VERIFIED",
    }:
        for line in content.splitlines():
            if not re.search(r"母公司.{0,40}可供分配.{0,40}(?:储备|儲備)", line):
                continue
            if re.search(r"未披露|未核验|无法核验|候选|不可确认|不能确认|不得计入", line):
                continue
            if re.search(r"\d|构成|上限|已披露|confirmed|verified", line, re.I):
                findings.append("母公司可供分配储备未核验，禁止写成已披露金额或现金分配上限")
                break
    for desc in findings:
        if any(item.get("rule") == "DECISION_RELIABILITY_LANGUAGE" and item.get("desc") == desc
               for item in audit.get("violations", [])):
            continue
        audit.setdefault("violations", []).append({
            "rule": "DECISION_RELIABILITY_LANGUAGE",
            "severity": "error", "desc": desc,
        })
        audit["error_count"] = int(audit.get("error_count", 0)) + 1
        audit["passed"] = False
        audit["verdict"] = "fail"


def _enforce_graham_block(audit: dict[str, Any], content: str, chapter_index: int) -> None:
    """Ch12 缺综合派 V_final 块时，注入 error 违规并判 fail（就地修改 audit）。"""
    if int(chapter_index) != 12:
        return
    if not _GRAHAM_LITE_DOC.exists():
        return  # 框架未装载，降级不强制
    missing = [m for m in _GRAHAM_BLOCK_MARKERS if m not in content]
    if not missing:
        return
    violation = {
        "rule": "GRAHAM_VFINAL_MISSING",
        "severity": "error",
        "desc": (
            "Ch12 缺综合派 V_final 估值块（裁决层），缺失标记：" + "、".join(missing) +
            "。必须补齐六路由→IV(用r*)→分红率→V_cash(同用r*)→λ五档→V_final→回报安全边际。"
        ),
    }
    audit.setdefault("violations", []).append(violation)
    audit["error_count"] = int(audit.get("error_count", 0)) + 1
    audit["passed"] = False
    audit["verdict"] = "fail"
    repair = audit.get("repair_plan")
    repair_line = "补写「综合派 V_final 估值（裁决层）」小节：" + "、".join(missing)
    if isinstance(repair, list):
        repair.append(repair_line)
    elif isinstance(repair, str) and repair:
        audit["repair_plan"] = repair + "\n" + repair_line
    else:
        audit["repair_plan"] = repair_line


# AV 有形侧必须逐行 bridge（D1）——防 DeepSeek 图省事取"归母净资产"一坨当资产价值。
# 只在综合派块已存在（说明 AV 段本该出现）且 canonical 框架装载时才强制，blast radius 限 Ch12。
_AV_TANGIBLE_MARKERS = ["货币资金", "应收账款", "存货", "固定资产"]


def _enforce_av_bridge(audit: dict[str, Any], content: str, chapter_index: int) -> None:
    """Ch12 有 AV 段却把有形侧塌成净资产一坨时，注入 error 逼逐行重估（就地改 audit）。"""
    if int(chapter_index) != 12:
        return
    if not _GRAHAM_LITE_DOC.exists():
        return  # 框架未装载，降级不强制
    # 仅当综合派块存在（AV 本该逐项出现）才检查；否则交给 _enforce_graham_block 先补块。
    if not any(m in content for m in _GRAHAM_BLOCK_MARKERS):
        return
    present = [m for m in _AV_TANGIBLE_MARKERS if m in content]
    # 至少要出现 3/4 有形行项才算逐行 bridge；不足即判定为"净资产一坨"偷懒。
    if len(present) >= 3:
        return
    violation = {
        "rule": "GRAHAM_AV_LUMPED",
        "severity": "error",
        "desc": (
            "AV 有形侧未逐行重估（仅见行项 " + "、".join(present or ["无"]) +
            "）。禁止用『归母净资产』一坨当有形 AV——用 search_report(query=\"货币资金 应收账款 存货 固定资产\") 从年报抓行项，"
            "至少列出 货币资金/应收账款/存货/固定资产 的账面→重置 bridge（应收扣坏账、存货乘行业系数、固资乘通胀因子）。"
        ),
    }
    audit.setdefault("violations", []).append(violation)
    audit["error_count"] = int(audit.get("error_count", 0)) + 1
    audit["passed"] = False
    audit["verdict"] = "fail"
    repair = audit.get("repair_plan")
    repair_line = "补写 AV 有形侧逐行 bridge：货币资金/应收账款/存货/固定资产 账面→重置各一行"
    if isinstance(repair, list):
        repair.append(repair_line)
    elif isinstance(repair, str) and repair:
        audit["repair_plan"] = repair + "\n" + repair_line
    else:
        audit["repair_plan"] = repair_line


def _enforce_av_method(audit: dict[str, Any], content: str, chapter_index: int) -> None:
    """Ch12 AV 用「Σ有形 − 负债合计」法时触发 error（就地修改 audit）。

    正确做法：归母净资产(账面) 为增量法基地，仅加各行调整增量，绝不减全额负债。
    反例（新型变种）：列出6行资产合计+无形重建 − 负债合计 → AV = 267亿（与旧错误等价）。

    检测逻辑：
      - AV_going 公式行（含 "=" 和 "AV_going"）内含「负债」字样 → 直接用了负债合计
      - 或：公式行±15行窗口内缺少「归母净资产」作为增量基地
    两条满足其一即 FAIL。
    """
    if int(chapter_index) != 12:
        return
    if not _GRAHAM_LITE_DOC.exists():
        return
    # 只有综合派块存在才检查（否则 VFINAL_MISSING 先触发）
    if not any(m in content for m in _GRAHAM_BLOCK_MARKERS):
        return
    # 只有有形行项已逐行列出（≥3/4）才检查方法；否则 LUMPED 先触发
    present = [m for m in _AV_TANGIBLE_MARKERS if m in content]
    if len(present) < 3:
        return

    lines = content.splitlines()
    av_going_indexes: list[int] = []
    # 只认「AV_going =」这种公式左值行（= 紧跟其后，容忍空格/加粗标记），
    # 不认结论摘要里「AV_going增量法≈2062亿」这类夹在句中的提及（其 = 来自 EPV=… 等旁词）。
    av_formula_re = re.compile(r"AV_going\s*[=＝]")
    for i, line in enumerate(lines):
        if av_formula_re.search(line):
            av_going_indexes.append(i)
    if not av_going_indexes:
        return  # 找不到公式行，跳过

    # 摘要里也可能先出现 ``AV_going = 1538M``，真正的完整公式在后文。
    # 只要任一候选公式附近存在归母净资产基地且公式本身不减负债，就证明方法正确；
    # 不能因第一个摘要命中而把后文完整 bridge 判成失败。
    candidate_checks: list[tuple[bool, bool]] = []
    for av_going_idx in av_going_indexes:
        av_line = lines[av_going_idx]
        window_start = max(0, av_going_idx - 30)
        window_end = min(len(lines), av_going_idx + 16)
        window = "\n".join(lines[window_start:window_end])
        uses_liabilities = "负债" in av_line
        has_book_equity = bool(re.search(r"归母净资产", window))
        candidate_checks.append((uses_liabilities, has_book_equity))
        if not uses_liabilities and has_book_equity:
            return

    uses_liabilities_in_formula = any(item[0] for item in candidate_checks)
    has_book_equity_base = any(item[1] for item in candidate_checks)

    desc_parts: list[str] = []
    if uses_liabilities_in_formula:
        desc_parts.append(
            "AV_going 公式行含「负债」——仍在用 Σ有形+无形 − 负债合计，"
            "即使行项逐一列出，减全额负债依旧导致 AV 系统性腰斩"
        )
    if not has_book_equity_base:
        desc_parts.append(
            "公式附近30行内未见「归母净资产」——缺少增量法基地"
        )

    violation = {
        "rule": "GRAHAM_AV_METHOD",
        "severity": "error",
        "desc": (
            "AV 计算方法违规（新型漏资产）：" + "；".join(desc_parts) + "。"
            "铁律：AV_going = 归母净资产(账面) "
            "− 账面虚项(商誉+无形账面值) "
            "+ Σ有形重置增量(仅调整差额，非全额) "
            "+ 表外无形重建。"
            "切勿「Σ列出资产 + 无形重建 − 负债合计」——列不全资产但减全额负债，"
            "格力示例：1952+731−2416=267亿（错）vs 1459−103+14+731=2101亿（对）。"
        ),
    }
    audit.setdefault("violations", []).append(violation)
    audit["error_count"] = int(audit.get("error_count", 0)) + 1
    audit["passed"] = False
    audit["verdict"] = "fail"
    repair_line = (
        "重算 AV（增量法）：以「归母净资产(账面)=X亿」为基地，"
        "逐行写有形重置增量（仅差额，非全额），"
        "剔除商誉+无形账面值，最后加表外无形重建——"
        "禁止再出现「合计−负债合计」结构。"
    )
    repair = audit.get("repair_plan")
    if isinstance(repair, list):
        repair.append(repair_line)
    elif isinstance(repair, str) and repair:
        audit["repair_plan"] = repair + "\n" + repair_line
    else:
        audit["repair_plan"] = repair_line


def _audit_content(content: str, chapter_index: int = 0) -> dict[str, Any]:
    """对内容运行可编程审计规则 — V12 使用 Dayu 移植的完整审计系统。

    对接 ``audit_rules.run_audit()``。
    """
    try:
        from scripts.audit_rules import run_audit
    except ModuleNotFoundError:
        from audit_rules import run_audit

    result = run_audit(content, skeleton="", chapter_index=chapter_index)

    violations = [
        {"rule": v.rule_code, "severity": v.severity, "desc": v.description}
        for v in result.violations
    ]
    errors = [v for v in violations if v["severity"] == "error"]
    warns = [v for v in violations if v["severity"] == "warn"]

    return {
        "violations": violations,
        "error_count": len(errors),
        "warn_count": len(warns),
        "passed": result.verdict.value == "pass",
        "verdict": result.verdict.value,
        "repair_plan": result.repair_plan,
    }


def _run_quality_checks(report_text: str, output_dir: str) -> dict[str, Any]:
    """V12: 运行 quality_gate + evidence_citation 后置检查。"""
    result: dict[str, Any] = {"passed": True, "issues": [], "warnings": []}

    # 1. 基础质量门禁
    try:
        try:
            from scripts.quality_gate import check as quality_check
        except ModuleNotFoundError:
            from quality_gate import check as quality_check
        qg = quality_check(report_text)
        if qg.get("status") == "BLOCKED":
            result["passed"] = False
            result["issues"].extend(qg.get("blocks", []))
        result["warnings"].extend(qg.get("warns", []))
        result["quality_gate"] = qg
    except Exception as e:
        result["warnings"].append(f"quality_gate error: {e}")

    # 2. 证据锚点验证（在脚注化前执行）
    try:
        try:
            from scripts.evidence_citation import MIN_EVIDENCE_COVERAGE_RATIO, validate_evidence_coverage
        except ModuleNotFoundError:
            from evidence_citation import MIN_EVIDENCE_COVERAGE_RATIO, validate_evidence_coverage
        try:
            from scripts.evidence_citation import EvidenceRegistry
        except ModuleNotFoundError:
            from evidence_citation import EvidenceRegistry
        registry = EvidenceRegistry()
        registry.register_from_output_dir(output_dir)
        cov = validate_evidence_coverage(report_text, registry)
        ratio = cov.get("coverage_ratio")
        if ratio is not None and ratio < MIN_EVIDENCE_COVERAGE_RATIO:
            result["passed"] = False
            result["issues"].append(
                f"证据覆盖率过低: {ratio:.1%} "
                f"< {MIN_EVIDENCE_COVERAGE_RATIO:.0%}"
            )
        if cov.get("unknown_sources", 0):
            result["passed"] = False
            result["issues"].append(
                f"存在未归一证据来源: {cov.get('unknown_sources')} 个"
            )
        result["evidence_coverage"] = cov
    except Exception as e:
        result["warnings"].append(f"evidence_citation error: {e}")

    # 2.5. Zone B 数据使用率检查
    try:
        import os as _os, json as _json
        zone_b_files = ["mda.json", "segments.json", "risks.json", "governance.json", "audit.json"]
        zone_b_available = []
        for zf in zone_b_files:
            path = _os.path.join(output_dir, zf)
            if _os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        data = _json.load(f)
                    # 检查是否薄数据
                    has_content = False
                    for v in data.values():
                        if isinstance(v, list) and len(v) > 0:
                            if not all(isinstance(x, str) and ("⚠️" in x or "无提取" in x) for x in v):
                                has_content = True
                                break
                        elif isinstance(v, dict) and v:
                            has_content = True
                            break
                        elif isinstance(v, str) and v.strip() and "⚠️" not in v:
                            has_content = True
                            break
                    if has_content:
                        zone_b_available.append(zf)
                except Exception:
                    pass
        # 检查报告中是否引用了可用的 Zone B 文件
        if zone_b_available:
            canonical_sources = set(registry.extract_canonical_sources(report_text))
            used = [zf for zf in zone_b_available if zf in canonical_sources]
            if len(used) < len(zone_b_available) * 0.5:
                result["warnings"].append(
                    f"Zone B 使用率低: {len(used)}/{len(zone_b_available)} 可用文件被引用 "
                    f"({', '.join(zone_b_available)})"
                )
            result["zone_b_usage"] = {"available": zone_b_available, "used": used}
    except Exception as e:
        result["warnings"].append(f"zone_b_check error: {e}")

    # 3. enhanced_quality_gate: 结论一致性 + 风险披露 + Token效率
    try:
        try:
            from scripts.enhanced_quality_gate import enhanced_check
        except ModuleNotFoundError:
            from enhanced_quality_gate import enhanced_check
        cb_path = os.path.join(output_dir, "compute_bundle.json")
        cb = None
        if os.path.exists(cb_path):
            import json
            with open(cb_path) as f:
                cb = json.load(f)
        eq = enhanced_check(report_text, audit_results=None, compute_bundle=cb)
        if eq.get("status") == "BLOCKED":
            result["passed"] = False
            result["issues"].extend(eq.get("blocks", []))
        result["warnings"].extend(eq.get("warns", []))
        result["enhanced_quality_gate"] = eq
    except Exception as e:
        result["warnings"].append(f"enhanced_quality_gate error: {e}")

    # 4. P2: 数据缺口扫描
    try:
        try:
            from scripts.data_gap_scanner import scan_report
        except ModuleNotFoundError:
            from data_gap_scanner import scan_report
        gaps = scan_report(report_text)
        if gaps.get("gaps"):
            result["warnings"].append(f"数据缺口: {len(gaps['gaps'])} 处 ⚠️ 标记")
            result["data_gaps"] = gaps
    except Exception as e:
        result["warnings"].append(f"data_gap_scanner error: {e}")

    # 5. V12 Content Audit：程序化内容深度检查（对标海螺报告）
    # v13+: 章节在 chapters/ 子目录；兼容旧版根目录
    _ch_scan_dir = os.path.join(output_dir, CHAPTERS_SUBDIR)
    if not os.path.isdir(_ch_scan_dir) or not any(
        f.startswith("_ch") and f.endswith(".md") for f in os.listdir(_ch_scan_dir)
    ):
        _ch_scan_dir = output_dir
    for ch_file in sorted(f for f in os.listdir(_ch_scan_dir) if f.startswith("_ch") and f.endswith(".md")):
        try:
            ch_text = open(os.path.join(_ch_scan_dir, ch_file)).read()
            ch_idx = int(ch_file.replace("_ch", "").replace(".md", ""))
            # 5a. M fallback 检查（GG 章 ~ch11）
            m_text = ch_text.lower().replace("非 fallback", "").replace("not fallback", "").replace("不是 fallback", "")
            if ch_idx in (11, 12) and ("fallback" in m_text or "M=0.7" in ch_text or "行业默认" in ch_text):
                fallback_disclosed = (
                    ("可靠性" in ch_text or "局限" in ch_text or "样本数" in ch_text)
                    and ("Normalized" in ch_text or "FCFE" in ch_text or "校正" in ch_text)
                )
                if not fallback_disclosed:
                    result["warnings"].append(
                        f"Ch{ch_idx}: M 值使用 fallback/行业默认但未披露可靠性；"
                        "请同时展示可用的 FCFE/Normalized 参考口径。"
                    )
            # 5b. 关联交易量化检查（治理章 ~ch09）
            if ch_idx in (8, 9) and "关联交易" in ch_text:
                if not re.search(r"\d+[\.\d]*\s*(百万元|亿元|M|亿|万)", ch_text):
                    result["warnings"].append(f"Ch{ch_idx}: 关联交易分析缺具体金额，请用 get_financial_statement 补充定量数据")
            # 5c. GG/DDM 前提差异（决策章 ~ch14）
            if ch_idx in (13, 14) and "一致" in ch_text:
                premise_analysis = (
                    "隐含 PE" in ch_text or "估值逻辑" in ch_text or "前提" in ch_text
                    or ("利润" in ch_text and "分红" in ch_text)
                )
                if not premise_analysis:
                    result["warnings"].append(f"Ch{ch_idx}: GG 和 DDM 估值逻辑前提不同（GG看利润/DDM看分红），请分析两者隐含假设差异")
            # 5d. V12.15: 少数股东治理张力检查（治理章 ~ch08）
            if ch_idx == 8:
                bundle_path = os.path.join(output_dir, "compute_bundle.json")
                if os.path.exists(bundle_path):
                    import json as _json
                    with open(bundle_path) as f:
                        bundle = _json.load(f)
                    minority = bundle.get("factor3", {}).get("minority_adjustment")
                    if minority and minority.get("trigger"):
                        if "少数股东" not in ch_text and "治理张力" not in ch_text:
                            result["warnings"].append(
                                f"Ch8: compute_bundle 存在 minority_adjustment (parent_ratio={minority.get('parent_ratio_3y', '?')})，"
                                "但 Ch8 未讨论少数股东治理张力。请加入'少数股东结构与治理张力'子节。"
                            )
            # 5e. V12.15: 治理折价引用检查（GG章 ~ch11）
            if ch_idx == 11:
                gt_path = os.path.join(output_dir, "governance_tension.json")
                if os.path.exists(gt_path):
                    import json as _json
                    with open(gt_path) as f:
                        gt = _json.load(f)
                    gov_discount = gt.get("governance_discount", {})
                    if isinstance(gov_discount, dict) and gov_discount.get("additional_discount_pct", 0) > 0:
                        if "治理折价" not in ch_text and "governance_discount" not in ch_text:
                            result["warnings"].append(
                                f"Ch11: governance_tension.json 存在治理折价 "
                                f"({gov_discount.get('additional_discount_pct')}%)，"
                                "但 Ch11 未引用治理折价分析。请加入'(13)治理折价与少数股东调整'步骤。"
                            )
            # 5f. V12.17: 分红事实检查——报告或Zone B说零分红但DB有分红
            zero_dividend_claim = re.search(
                r"零分红(?!率)|不分红(?!率)|停止分红(?!率)|无分红(?!率)|股息每股\s*0(?:\.0+)?(?![\d.])|"
                r"DPS\s*=\s*0(?:\.0+)?(?![\d.])",
                ch_text,
            )
            if zero_dividend_claim:
                bundle_path = os.path.join(output_dir, "compute_bundle.json")
                if os.path.exists(bundle_path):
                    import json as _json
                    with open(bundle_path) as f:
                        bundle = _json.load(f)
                    dps = bundle.get("params", {}).get("dps_fy") or bundle.get("params", {}).get("DPS") or 0
                    if dps > 0.01:
                        result["warnings"].append(
                            f"Ch{ch_idx}: 报告/ZoneB声称零分红(DPS=0)，但 compute_bundle 显示 DPS={dps}。"
                            "Zone B mda.json 可能提取错误，请以 compute_bundle 为准修正分红相关论述。"
                        )
        except Exception:
            pass
    try:
        from turtle_agent.tools.calc_tools import compute_gg, compute_aa
        gg = compute_gg(output_dir)
        aa = compute_aa(output_dir)
        # 6a. GG 数字对账：复用 report_audit 的指标身份分类，只核对
        # 明确标为 base/AA 口径的 GG，排除 FCFE、Normalized、情景和阈值。
        try:
            from scripts.report_audit import extract_data_points
        except ModuleNotFoundError:
            from report_audit import extract_data_points
        gg_points = [
            point for point in extract_data_points(report_text)
            if point.get("inferred_field") == "GG"
            and "base" in set(point.get("metric_tags", []))
            and not {"fcfe", "normalized", "discounted"}.intersection(point.get("metric_tags", []))
        ]
        gg_tool = gg.get("gg_base")
        if gg_tool and gg_points:
            for point in gg_points:
                val = float(point["reported_value"])
                if abs(val - gg_tool) > 1.0:  # 偏差 >1pp
                    result["warnings"].append(
                        f"事实对账: L{point['line_number']} base GG={val}%，"
                        f"工具计算GG={gg_tool}%，偏差>1pp"
                    )
        # 6b. AP/DPO 对账
        ap = aa.get("ap_driven_analysis", {})
        if ap.get("ap_normal") or ap.get("ap_pct") == 0:
            def _has_unnegated_term(sentence: str, term: str) -> bool:
                for match in re.finditer(re.escape(term), sentence, re.IGNORECASE):
                    prefix = sentence[max(0, match.start() - 40):match.start()]
                    suffix = sentence[match.end():match.end() + 16]
                    if re.search(r"(?:无|不存在|未见|不构成|不触发|未触发|没有)[^。；\n]{0,36}$", prefix):
                        continue
                    if re.match(r"\s*(?:风险|问题)?\s*(?:为|=|：|:)?\s*(?:零|0(?:\.0+)?%)", suffix):
                        continue
                    return True
                return False

            ap_problem = any(
                _has_unnegated_term(sentence, term)
                for sentence in re.split(r"[。；\n]", report_text)
                for term in ("伪现金流", "DPO拉长", "AP延迟")
            )
            if ap_problem:
                result["warnings"].append("事实对账: 报告称AP/DPO恶化/伪现金流，但compute_aa显示DPO改善、AP正常(0%伪现金流)。请修正。")
        # 6c. PE 对账：报告中的 PE vs compute_bundle 计算的 PE
        pe_in_report = re.findall(
            r"(?:当前|现价对应|本期)\s*PE[≈=约：:]?\s*(\d+\.?\d*)\s*[倍xX]",
            report_text,
            flags=re.IGNORECASE,
        )
        pe_tool = cb.get("factor4", {}).get("current_pe") if cb else None
        if pe_tool and pe_in_report:
            for val in pe_in_report:
                if abs(float(val) - pe_tool) > 1.0:
                    result["warnings"].append(
                        f"事实对账: 报告中PE≈{val}x，compute_bundle计算PE={pe_tool:.1f}x，偏差>1x。"
                        "请检查是否混用了不同口径的MC或NP（RMB vs HKD）。"
                    )

        # 6d. 分红事实对账：报告说零分红但实际有分红
        if re.search(r"零分红(?!率)|不分红(?!率)|停止分红(?!率)", report_text):
            dps = cb.get("params", {}).get("dps_fy") or cb.get("params", {}).get("DPS") or 0 if cb else 0
            if dps and dps > 0.01:
                result["warnings"].append(
                    f"事实对账: 报告声称零分红/不分红，但 compute_bundle 显示 DPS={dps}。"
                    "请检查分红相关章节（Ch7/Ch11/Ch12）并修正。"
                )

        # 6d. OCF/NP 口径对账
        ocf_np_analysis = cb.get("factor2", {}).get("ocf_np_analysis", {}) if cb else {}
        ocf_np_raw = ocf_np_analysis.get("raw_mean")
        if ocf_np_raw:
            mean_mentions = re.findall(
                r"OCF\s*/\s*NP(?:\s*(?:均值|平均|原始口径))?\s*[≈=约]?\s*(\d+\.?\d*)",
                report_text,
            )
            mean_mentions.extend(re.findall(
                r"raw_mean\s*[≈=约：:]?\s*(\d+\.?\d*)",
                report_text,
                flags=re.IGNORECASE,
            ))
            raw_mean_disclosed = any(
                abs(float(value) - ocf_np_raw) / max(ocf_np_raw, 0.01) <= 0.1
                for value in mean_mentions
            )
            warned_values: set[str] = set()
            for line in report_text.splitlines():
                # A disclosed single-year ratio is not the multi-year raw mean.
                if re.search(r"(?:FY)?20\d{2}|本年|当年|本期", line):
                    continue
                for val in re.findall(r"OCF\s*/\s*NP\s*[≈=约]?\s*(\d+\.?\d*)", line):
                    if val in warned_values:
                        continue
                    if not raw_mean_disclosed and abs(float(val) - ocf_np_raw) / max(ocf_np_raw, 0.01) > 0.3:
                        warned_values.add(val)
                        result["warnings"].append(
                            f"事实对账: 报告中OCF/NP≈{val}，compute_bundle原始均值={ocf_np_raw}，偏差>30%。"
                            "请检查是否使用了调整后口径，若是必须在首次出现处标注'扰动调整后口径'。"
                        )

        # 6e. M 来源对账
        m_ingredient = gg.get("ingredients", {}).get("M", {})
        if "computed_from" in str(m_ingredient.get("source", "")):
            if "fallback" in report_text or "行业默认" in report_text:
                result["warnings"].append(f"事实对账: 报告称M=fallback，但compute_gg已从实际DPS/EPS计算M={m_ingredient.get('value')}。请删除'fallback'相关表述。")
        # 6d. V12.15: 治理折价事实对账
        try:
            gt_path = os.path.join(output_dir, "governance_tension.json")
            if os.path.exists(gt_path):
                import json as _json
                with open(gt_path) as f:
                    gt = _json.load(f)
                gov_discount = gt.get("governance_discount", {})
                if isinstance(gov_discount, dict):
                    gt_disc = gov_discount.get("additional_discount_pct", 0)
                    if gt_disc > 0:
                        # 检查报告中是否提及了治理折价
                        if "治理折价" not in report_text and "governance discount" not in report_text.lower():
                            result["warnings"].append(
                                f"事实对账: governance_tension.json 治理折价={gt_disc}%，"
                                "但报告中未提及治理折价。请检查 Ch8/Ch11 是否缺失了治理张力分析。"
                            )
        except Exception:
            pass
        # 6e. 股息身份硬对账：DPS 先按币种归一，再与交易币种价格比较。
        dividend_check = _check_dividend_identity(report_text, cb or {})
        result["dividend_identity"] = dividend_check
        if dividend_check["status"] == "FAIL":
            result["passed"] = False
            examples = dividend_check["contradictions"][:4]
            found = ", ".join(
                f"L{x['line']}={x['reported_yield_pct']}%" for x in examples
            )
            chapters = ",".join(
                f"Ch{x}" for x in sorted({item["chapter"] for item in dividend_check["contradictions"]})
            )
            result["issues"].append(
                "dividend_identity: 当前股息率与 canonical "
                f"{dividend_check['expected_yield_pct']:.2f}% 不一致；chapters={chapters}（{found}）"
            )
    except Exception:
        pass

    return result


def _collect_sources(output_dir: str) -> list[str]:
    """从所有章节文件中收集 [source: X] 引用。"""
    sources: set[str] = set()
    for f in sorted(os.listdir(output_dir)):
        if f.startswith("_ch") and f.endswith(".md"):
            path = os.path.join(output_dir, f)
            with open(path, encoding="utf-8") as fh:
                sources.update(
                    re.findall(r"\[(?:table-)?source:\s*([^\]]+)\]", fh.read(), re.IGNORECASE)
                )
    return sorted(sources)


write_chapter._tool_meta = {"name": "write_chapter", "description": "写入单章内容(含自动审计S1/E1/C2)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "chapter_index": {"type": "integer", "description": "章序号0-14"}, "title": {"type": "string", "description": "章节标题"}, "content": {"type": "string", "description": "Markdown章节内容"}, "force_rewrite": {"type": "boolean", "description": "质量修复轮强制覆盖已有章节", "optional": True}}}  # type: ignore[attr-defined]
verify_official_fact._tool_meta = {
    "name": "verify_official_fact",
    "description": "把read_section精确回读的原文事实程序化验证为VERIFIED observation。quote必须逐字存在于指定doc_id/page，数值raw_value也必须出现在quote；失败不得自行升级。",
    "parameters": {
        "output_dir": {"type": "string", "description": "股票输出目录"},
        "doc_id": {"type": "string", "description": "read_section返回的document_id"},
        "page": {"type": "integer"},
        "fact_name": {"type": "string", "description": "稳定英文事实身份"},
        "domain": {"type": "string", "description": "audit/financial/operations/governance/industry/capital_allocation等"},
        "raw_value": {"type": ["number", "string", "boolean"]},
        "normalized_value": {"type": ["number", "string", "boolean"]},
        "unit": {"type": "string"},
        "basis": {"type": "string"},
        "quote": {"type": "string", "description": "指定页逐字原文，不得概括"},
        "currency": {"type": "string", "optional": True}
    }
}  # type: ignore[attr-defined]
write_decision_manifest._tool_meta = {"name": "write_decision_manifest", "description": "提交结构化最终决策；必须在 assemble_report 前调用，Ch0/Ch14/数据库以此为准", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "qualitative_decision": {"type": "string", "enum": ["continue", "pause", "abandon"]}, "quantitative_decision": {"type": "string", "enum": ["buy", "hold", "avoid"]}, "position_pct": {"type": "number", "description": "建议仓位百分比，观察仓也要填写"}, "qualitative_rationale": {"type": "string", "optional": True}, "quantitative_rationale": {"type": "string", "optional": True}, "monitor_triggers": {"type": "array", "items": {"type": "string"}, "optional": True}, "exit_conditions": {"type": "array", "items": {"type": "string"}, "optional": True}}}  # type: ignore[attr-defined]
write_decision_ledger._tool_meta = {
    "name": "write_decision_ledger",
    "description": "提交V3全报告唯一决策参数账本；正文关键值必须用[decision: entry_id]绑定，冻结后局部修复不可漂移",
    "parameters": {
        "output_dir": {"type": "string", "description": "股票输出目录"},
        "entries": {
            "type": "array",
            "description": "15类canonical决策参数条目",
            "items": {
                "type": "object",
                "properties": {
                    "entry_id": {"type": "string"},
                    "metric_id": {"type": "string", "enum": [
                        "market.price.current", "return.gg.base", "return.gg.fcfe",
                        "return.gg.normalized", "hurdle.ii", "valuation.v_final",
                        "moat.lambda", "return.required", "moat.decay", "margin.price",
                        "margin.return", "decision.position.recommended", "trigger.buy",
                        "trigger.reduce", "trigger.exit"
                    ]},
                    "value": {"type": ["number", "string", "boolean"]},
                    "unit": {"type": "string"},
                    "scenario": {"type": "string"},
                    "basis": {"type": "string"},
                    "as_of": {"type": "string"},
                    "version": {"type": "integer"},
                    "status": {"type": "string", "enum": ["active", "deprecated"]},
                    "chapters": {"type": "array", "items": {"type": "integer"}},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                    "affects_action": {"type": "boolean"},
                    "canonical": {"type": "boolean", "description": "同一metric存在多情景时，显式指定唯一最终口径"},
                    "rationale": {"type": "string"},
                    "deprecation_reason": {"type": "string"},
                    "superseded_by": {"type": "string"}
                },
                "required": ["entry_id", "metric_id", "value", "unit", "scenario", "basis", "as_of", "version", "status", "chapters", "source_ids", "affects_action"]
            }
        },
        "change_reason": {"type": "string", "description": "本版参数及动作相对上一版的变更原因；首次生成写initial analysis"},
        "freeze": {"type": "boolean", "description": "首次无账本时先false保存reviewable草案并获取锚点缺口；补齐后再true冻结", "optional": True}
    }
}  # type: ignore[attr-defined]
write_claim_evidence_ledger._tool_meta = {
    "name": "write_claim_evidence_ledger",
    "description": "提交V3重大主张证据链；直接支持必须是原子事实，其每个实质数字均逐字存在于绑定VERIFIED观察，复合事实须拆行；同时校验来源权威性×主张距离、口径日期、循环引用和决策影响",
    "parameters": {
        "output_dir": {"type": "string", "description": "股票输出目录"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "claim": {"type": "string"},
                    "chapters": {"type": "array", "items": {"type": "integer"}},
                    "raw_facts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "evidence_id": {"type": "string"},
                                "observation_id": {"type": "string", "description": "官方原始事实直接支持引用VERIFIED observation_id"},
                                "calculation_id": {"type": "string", "description": "派生计算直接支持引用CALC identity；不得与observation_id同时使用"},
                                "source_id": {"type": "string"},
                                "source_group_id": {"type": "string"},
                                "fact": {"type": "string", "description": "一个原子事实；其中每个实质数字必须出现在observation原文/值中，不能借用同文档无关OBS，复合数字拆成多条evidence"},
                                "authority": {"type": "string", "enum": ["audited_filing", "company_filing", "official_statistics", "industry_data", "media", "other", "verified_calculation"]},
                                "claim_distance": {"type": "string", "enum": ["raw_data", "direct_statement", "secondary_summary", "analysis", "rumor"]},
                                "published_at": {"type": "string"},
                                "data_as_of": {"type": "string"},
                                "direct_support": {"type": "boolean"},
                                "support_type": {"type": "string", "enum": ["supports", "contradicts", "context"]},
                                "basis_match": {"type": "string", "enum": ["exact", "compatible", "uncertain", "mismatch"]},
                                "conflict_of_interest": {"type": "string"},
                                "cross_checked_by": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["evidence_id", "source_id", "source_group_id", "fact", "authority", "claim_distance", "published_at", "data_as_of", "direct_support", "support_type", "basis_match", "conflict_of_interest"]
                        }
                    },
                    "reasoning_steps": {"type": "array", "items": {"type": "string"}},
                    "alternative_explanations": {"type": "array", "items": {"type": "string"}},
                    "applicability_conditions": {"type": "array", "items": {"type": "string"}},
                    "confidence": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "enum": ["frequency", "base_rate", "analyst_subjective", "scenario_weight"]},
                            "value": {"type": "number"},
                            "basis": {"type": "string"},
                            "interval": {"type": "array", "items": {"type": "number"}}
                        },
                        "required": ["kind", "value", "basis"]
                    },
                    "decision_impact": {
                        "type": "object",
                        "properties": {
                            "valuation": {"type": "string"},
                            "position": {"type": "string"},
                            "action": {"type": "string"}
                        },
                        "required": ["valuation", "position", "action"]
                    },
                    "decision_entry_ids": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["claim_id", "claim", "chapters", "raw_facts", "reasoning_steps", "alternative_explanations", "applicability_conditions", "confidence", "decision_impact", "decision_entry_ids"]
            }
        },
        "change_reason": {"type": "string"},
        "freeze": {"type": "boolean", "description": "首次无账本先false，按validation补锚点后再true", "optional": True},
        "resume_last_rejected": {"type": "boolean", "description": "复用上次完整被拒载荷，避免重新生成整本账本；与下面的最小补丁参数配合", "optional": True},
        "drop_evidence_ids": {"type": "array", "items": {"type": "string"}, "description": "从上次被拒载荷删除验证明确判错的evidence_id", "optional": True},
        "claim_chapter_additions": {"type": "array", "items": {"type": "object", "properties": {"claim_id": {"type": "string"}, "chapters": {"type": "array", "items": {"type": "integer"}}}, "required": ["claim_id", "chapters"]}, "description": "为已有主张补充缺失的适用章节，绑定仍由框架确定性完成", "optional": True}
    }
}  # type: ignore[attr-defined]
write_valuation_model_ledger._tool_meta = {
    "name": "write_valuation_model_ledger",
    "description": "按valuation_route提交V3估值模型适用性、口径、终值依赖、敏感性翻转、禁用模型理由和多模型独立性账本",
    "parameters": {
        "output_dir": {"type": "string"},
        "company_profile": {"type": "object", "properties": {
            "business_type": {"type": "string", "enum": ["general_operating", "bank", "insurer", "property_developer", "asset_holding", "cyclical", "utility", "pre_revenue_biotech", "conglomerate"]},
            "asset_intensity": {"type": "string", "enum": ["asset_light", "asset_heavy", "mixed"]},
            "archetype_id": {"type": "string"}, "valuation_route_id": {"type": "string"}, "registry_version": {"type": "string"},
            "valuation_route": {"type": "string"}, "route_reasoning": {"type": "string"}},
            "required": ["business_type", "asset_intensity", "archetype_id", "valuation_route_id", "registry_version", "valuation_route", "route_reasoning"]},
        "models": {"type": "array", "items": {"type": "object", "properties": {
            "model_id": {"type": "string"}, "route_model_id": {"type": "string", "description": "必须来自valuation_route models或rejected_models"}, "model_type": {"type": "string", "enum": ["DCF", "DDM", "EPV", "ASSET_VALUE", "NAV", "SOTP", "RETURN_DECOMPOSITION", "RELATIVE", "RESIDUAL_INCOME", "RNPV"]},
            "role": {"type": "string", "enum": ["primary", "corroborative", "stress"]}, "status": {"type": "string", "enum": ["active", "rejected"]},
            "chapters": {"type": "array", "items": {"type": "integer"}}, "independence_group_id": {"type": "string"}, "shared_assumption_ids": {"type": "array", "items": {"type": "string"}},
            "applicability": {"type": "object", "properties": {"business_fit": {"type": "string"}, "cash_flow_fit": {"type": "string"}, "capital_structure_fit": {"type": "string"}, "payout_fit": {"type": "string"}, "rationale": {"type": "string"}, "disqualifiers": {"type": "array", "items": {"type": "string"}}}, "required": ["business_fit", "cash_flow_fit", "capital_structure_fit", "payout_fit", "rationale", "disqualifiers"]},
            "basis": {"type": "object", "properties": {"value_scope": {"type": "string", "enum": ["equity", "enterprise"]}, "cash_flow_scope": {"type": "string"}, "currency": {"type": "string"}, "as_of": {"type": "string"}, "tax_basis": {"type": "string", "enum": ["pre_tax", "post_tax", "not_applicable"]}}, "required": ["value_scope", "cash_flow_scope", "currency", "as_of", "tax_basis"]},
            "assumptions": {"type": "object", "properties": {"forecast_years": {"type": "number"}, "discount_rate": {"type": "object", "properties": {"value_pct": {"type": "number"}, "kind": {"type": "string"}, "inflation_basis": {"type": "string"}, "tax_basis": {"type": "string"}}, "required": ["value_pct", "kind", "inflation_basis", "tax_basis"]}, "terminal_growth": {"type": "object", "properties": {"value_pct": {"type": "number"}, "inflation_basis": {"type": "string"}}}, "dividend_yield_pct": {"type": "number", "description": "RETURN_DECOMPOSITION必填"}, "growth_value_return_pct": {"type": "number", "description": "RETURN_DECOMPOSITION必填；不得重复计入已含增长的margin"}, "moat_decay_pct": {"type": "number"}, "required_return_pct": {"type": "number"}, "retained_value_realization": {"type": "number"}, "dps_hkd": {"type": "number"}}},
            "result": {"type": "object", "properties": {"value_per_share": {"type": "number"}, "currency": {"type": "string"}, "gross_return_pct": {"type": "number", "description": "RETURN_DECOMPOSITION=dividend_yield_pct+growth_value_return_pct"}, "return_safety_margin_pct": {"type": "number", "description": "gross-required_return_pct-moat_decay_pct"}}, "required": ["value_per_share"]},
            "equity_bridge": {"type": "object", "properties": {"enterprise_value": {"type": "number"}, "non_operating_assets": {"type": "number"}, "debt": {"type": "number"}, "minority_interest": {"type": "number"}, "other_adjustments": {"type": "number"}, "equity_value": {"type": "number"}, "shares": {"type": "number"}, "per_share_value": {"type": "number"}}},
            "terminal_value": {"type": "object", "properties": {"present_value": {"type": "number"}, "total_model_value": {"type": "number"}, "share_pct": {"type": "number"}}},
            "sensitivity_tests": {"type": "array", "items": {"type": "object", "properties": {"case_id": {"type": "string", "enum": ["discount_rate_up_1pp", "growth_down_1pp", "combined_stress"]}, "value_per_share": {"type": "number"}, "action": {"type": "string", "enum": ["buy", "hold", "avoid"]}}}},
            "fragility_mitigation": {"type": "string"}, "source_ids": {"type": "array", "items": {"type": "string"}}, "decision_entry_ids": {"type": "array", "items": {"type": "string"}}
        }, "required": ["model_id", "route_model_id", "model_type", "role", "status"]}},
        "synthesis": {"type": "object", "properties": {"action": {"type": "string", "enum": ["buy", "hold", "avoid"]}, "position_pct": {"type": "number"}, "range_low": {"type": "number"}, "range_base": {"type": "number"}, "range_high": {"type": "number"}, "chosen_value_per_share": {"type": "number"}, "decision_rule": {"type": "string"}, "divergence_explanation": {"type": "string"}, "decision_entry_id": {"type": "string"}}, "required": ["action", "position_pct", "range_low", "range_high", "chosen_value_per_share", "decision_rule", "divergence_explanation", "decision_entry_id"]},
        "cash_access_bridge": {"type": "object", "description": "现金法律实体/受限性/母公司可分配储备桥；未验证现金在主估值中必须100%折价", "properties": {
            "as_of": {"type": "string"}, "unit": {"type": "string"}, "gross_cash_amount": {"type": "number"}, "conservative_accessible_cash_amount": {"type": "number", "description": "若母公司可分派储备不是VERIFIED，必须为0；合并银行存款存在不等于外部股东法律可分配"},
            "components": {"type": "array", "items": {"type": "object", "properties": {
                "component_id": {"type": "string"}, "amount": {"type": "number"}, "access_status": {"type": "string", "enum": ["VERIFIED_ACCESSIBLE", "CONDITIONAL", "RESTRICTED", "RELATED_PARTY", "UNVERIFIED"]}, "legal_distributability": {"type": "string", "enum": ["VERIFIED", "CONDITIONAL", "NOT_VERIFIED"], "description": "母公司储备未披露时，合并现金应为NOT_VERIFIED且haircut_pct=100"}, "legal_owner_scope": {"type": "string"}, "haircut_pct": {"type": "number"}, "source_ids": {"type": "array", "items": {"type": "string", "description": "只允许当前VERIFIED OBS:/CALC:/EVD:身份，禁止DOC或自由文本"}}, "notes": {"type": "string"}
            }, "required": ["component_id", "amount", "access_status", "legal_distributability", "legal_owner_scope", "haircut_pct", "source_ids"]}},
            "parent_distributable_reserves": {"type": "object", "properties": {"status": {"type": "string", "enum": ["VERIFIED", "NOT_DISCLOSED", "NOT_APPLICABLE"]}, "amount": {"type": "number"}, "source_ids": {"type": "array", "items": {"type": "string"}}, "basis": {"type": "string"}}, "required": ["status", "source_ids"]},
            "ordinary_distribution_capacity": {"type": "object", "properties": {"amount": {"type": "number"}, "unit": {"type": "string"}, "basis_kind": {"type": "string", "enum": ["actual_distribution_flow", "legal_reserve_ceiling", "not_verified"], "description": "实际分红流、法律储备上限或未验证；储备上限不等于母公司现金位置"}, "source_ids": {"type": "array", "items": {"type": "string"}}, "basis": {"type": "string"}}, "required": ["amount", "basis_kind", "source_ids"]},
            "unresolved": {"type": "array", "items": {"type": "string"}}, "conclusion": {"type": "string"}
        }, "required": ["as_of", "unit", "gross_cash_amount", "conservative_accessible_cash_amount", "components", "parent_distributable_reserves", "ordinary_distribution_capacity", "unresolved", "conclusion"]},
        "parameter_calibrations": {"type": "array", "description": "λ和护城河衰减等关键参数；字段名必须严格匹配可靠性门", "items": {"type": "object", "properties": {
            "model_id": {"type": "string"}, "parameter": {"type": "string", "enum": ["retained_value_realization", "moat_decay_pct"]}, "value": {"type": "number"}, "method": {"type": "string", "enum": ["empirical", "historical_base_rate", "conservative_bound", "working_assumption"]}, "range_low": {"type": "number"}, "range_high": {"type": "number"}, "basis": {"type": "string"}, "source_ids": {"type": "array", "items": {"type": "string"}}, "decision_use": {"type": "string", "enum": ["primary", "corroborative", "diagnostic"]}, "market_price_inputs": {"type": "array", "items": {"type": "string"}}, "sensitivity": {"type": "object", "properties": {"action_at_low": {"type": "string"}, "action_at_high": {"type": "string"}}, "required": ["action_at_low", "action_at_high"]}
        }, "required": ["model_id", "parameter", "value", "method", "range_low", "range_high", "basis", "source_ids", "decision_use", "sensitivity"]}},
        "model_comparisons": {"type": "array", "description": "每个非主模型必须以model_id对against_model_id主模型比较", "items": {"type": "object", "properties": {
            "model_id": {"type": "string"}, "against_model_id": {"type": "string"}, "comparable": {"type": "boolean"}, "discount_rate_difference_pp": {"type": "number", "description": "仅双方都有适用折现率时填写；NAV等kind=not_applicable时必须省略，禁止0或-1哨兵"}, "allowed_use": {"type": "string", "enum": ["corroboration", "distribution_floor", "upper_bound", "stress", "diagnostic"]}, "basis_differences": {"type": "string"}
        }, "required": ["model_id", "against_model_id", "comparable", "allowed_use", "basis_differences"]}},
        "joint_stress_tests": {"type": "array", "description": "simultaneous_inputs必须含盈利、payout_ratio及cash_access_pct/retained_value_realization/accessible_cash_amount之一", "items": {"type": "object", "properties": {
            "case_id": {"type": "string"}, "description": {"type": "string"}, "simultaneous_inputs": {"type": "object", "properties": {"normalized_earnings": {"type": "number"}, "normalized_profit": {"type": "number"}, "owner_earnings": {"type": "number"}, "payout_ratio": {"type": "number"}, "cash_access_pct": {"type": "number"}, "retained_value_realization": {"type": "number"}, "accessible_cash_amount": {"type": "number"}}, "required": ["payout_ratio"]}, "output": {"type": "object", "properties": {"value_per_share": {"type": "number"}, "currency": {"type": "string"}, "action": {"type": "string", "enum": ["buy", "hold", "avoid"]}}, "required": ["value_per_share", "action"]}, "decision_implication": {"type": "string"}
        }, "required": ["case_id", "simultaneous_inputs", "output", "decision_implication"]}},
        "action_policy": {"type": "object", "description": "持有人/非持有人只填buy/hold/avoid；若不同则摩擦必须结构化量化", "properties": {
            "current_holders_action": {"type": "string", "enum": ["buy", "hold", "avoid"]}, "nonholders_action": {"type": "string", "enum": ["buy", "hold", "avoid"]}, "holder_specific_friction": {"type": "object", "properties": {"quantified_cost_pct": {"type": "number"}, "source_ids": {"type": "array", "items": {"type": "string"}}, "basis": {"type": "string"}}}, "precedence_order": {"type": "array", "items": {"type": "string"}, "minItems": 4}, "upgrade_requires": {"type": "string"}, "joint_stress_action": {"type": "string", "enum": ["buy", "hold", "avoid"]}
        }, "required": ["current_holders_action", "nonholders_action", "precedence_order", "upgrade_requires", "joint_stress_action"]},
        "semantic_resolutions": {"type": "array", "description": "migration semantic_frontier逐项研究裁决；无frontier时传空数组", "items": {"type": "object", "properties": {
            "model_id": {"type": "string"}, "field": {"type": "string"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "research_basis": {"type": "string"}, "mechanism": {"type": "string"},
            "valuation_impact": {"type": "string"}, "decision_impact": {"type": "string"}
        }, "required": ["model_id", "field", "evidence_ids", "research_basis", "mechanism", "valuation_impact", "decision_impact"]}},
        "resume_best_rejected": {"type": "boolean", "description": "为true时从同frontier最佳拒绝稿恢复；仅配合semantic_resolution_patches", "optional": True},
        "resume_last_rejected": {"type": "boolean", "description": "为true时从完整valuation_model_last_rejected恢复；只重传需修的顶层可靠性section，省略字段保持不变，合并后全量重验", "optional": True},
        "semantic_resolution_patches": {"type": "array", "description": "只提交当前validation findings涉及的完整resolution行；程序与最佳拒绝稿确定性合并后全量重验", "optional": True, "items": {"type": "object", "properties": {
            "model_id": {"type": "string"}, "field": {"type": "string"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "research_basis": {"type": "string"}, "mechanism": {"type": "string"},
            "valuation_impact": {"type": "string"}, "decision_impact": {"type": "string"}
        }, "required": ["model_id", "field", "evidence_ids", "research_basis", "mechanism", "valuation_impact", "decision_impact"]}},
        "change_reason": {"type": "string"},
        "freeze": {"type": "boolean", "description": "首次无账本先false，按validation补模型锚点后再true", "optional": True}
    }
}  # type: ignore[attr-defined]
write_thesis_test_ledger._tool_meta = {
    "name": "write_thesis_test_ledger",
    "description": "提交V3竞争性解释、区分性观察、阈值依据与概率身份账本",
    "parameters": {
        "output_dir": {"type": "string"},
        "competitive_tests": {"type": "array", "description": "竞争解释测试；字段名必须严格遵守schema", "items": {"type": "object", "properties": {
            "test_id": {"type": "string"}, "thesis_claim_id": {"type": "string"},
            "primary_explanation": {"type": "string"}, "strongest_alternative": {"type": "string"},
            "alternative_evidence_ids": {"type": "array", "items": {"type": "string"}},
            "discriminating_observations": {"type": "array", "minItems": 1, "items": {"type": "object", "properties": {
                "observation_id": {"type": "string"}, "metric": {"type": "string"},
                "availability": {"type": "string"}, "primary_prediction": {"type": "string"},
                "alternative_prediction": {"type": "string"}, "update_rule": {"type": "string"},
                "threshold_id": {"type": "string"}
            }, "required": ["observation_id", "metric", "availability", "primary_prediction", "alternative_prediction", "update_rule", "threshold_id"]}},
            "probability_set_id": {"type": "string"}, "primary_scenario_id": {"type": "string"},
            "alternative_scenario_id": {"type": "string"},
            "flip_condition": {"type": "object", "properties": {
                "threshold_id": {"type": "string"}, "basis": {"type": "string"}, "window": {"type": "string"}
            }, "required": ["threshold_id", "basis", "window"]},
            "valuation_after_flip": {"type": "number"}, "position_after_flip": {"type": "number"},
            "action_after_flip": {"type": "string", "enum": ["buy", "hold", "increase", "reduce", "avoid", "exit", "reassess"]},
            "decision_entry_ids": {"type": "array", "items": {"type": "string"}},
            "chapters": {"type": "array", "items": {"type": "integer"}}
        }, "required": ["test_id", "thesis_claim_id", "primary_explanation", "strongest_alternative", "alternative_evidence_ids", "discriminating_observations", "probability_set_id", "primary_scenario_id", "alternative_scenario_id", "flip_condition", "valuation_after_flip", "position_after_flip", "action_after_flip", "decision_entry_ids", "chapters"]}},
        "thresholds": {"type": "array", "description": "可审计监控阈值；discrimination_target必须为test_id或decision_rule", "items": {"type": "object", "properties": {
            "threshold_id": {"type": "string"}, "metric": {"type": "string"},
            "current_value": {"type": "number"}, "threshold_value": {"type": "number"}, "unit": {"type": "string"},
            "operator": {"type": "string", "enum": [">", ">=", "<", "<=", "==", "changes_to"]},
            "basis_type": {"type": "string", "enum": ["historical_volatility", "peer_benchmark", "model_sensitivity", "contractual", "accounting_regulatory", "base_rate", "expert_judgment"]},
            "basis_description": {"type": "string"}, "source_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "observation_frequency": {"type": "string"}, "window": {"type": "string"},
            "aggregation": {"type": "string", "enum": ["single_period", "rolling_average", "consecutive_periods", "cumulative"]},
            "seasonal_adjustment": {"type": "string", "enum": ["adjusted", "not_needed", "unavailable"]},
            "accounting_definition": {"type": "string"},
            "precision": {"type": "object", "properties": {"justified_decimals": {"type": "integer"}, "basis": {"type": "string"}}, "required": ["justified_decimals", "basis"]},
            "discrimination_target": {"type": "string"},
            "independent_validation": {"type": "string", "optional": True},
            "action": {"type": "string", "enum": ["buy", "hold", "increase", "reduce", "avoid", "exit", "reassess"]},
            "decision_entry_ids": {"type": "array", "items": {"type": "string"}},
            "chapters": {"type": "array", "items": {"type": "integer"}}
        }, "required": ["threshold_id", "metric", "current_value", "threshold_value", "unit", "operator", "basis_type", "basis_description", "source_ids", "observation_frequency", "window", "aggregation", "seasonal_adjustment", "accounting_definition", "precision", "discrimination_target", "action", "decision_entry_ids", "chapters"]}},
        "probability_sets": {"type": "array", "description": "互斥且完备的概率集合", "items": {"type": "object", "properties": {
            "set_id": {"type": "string"}, "mutually_exclusive": {"type": "boolean"},
            "collectively_exhaustive": {"type": "boolean"}, "resolution_due": {"type": "string"},
            "estimates": {"type": "array", "minItems": 2, "items": {"type": "object", "properties": {
                "scenario_id": {"type": "string"}, "label": {"type": "string"},
                "kind": {"type": "string", "enum": ["frequency", "base_rate", "analyst_subjective", "scenario_weight"]},
                "value": {"type": "number"}, "interval": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "number"}},
                "basis": {"type": "string"}, "source_ids": {"type": "array", "items": {"type": "string"}},
                "as_of": {"type": "string"}, "calibration_history_id": {"type": "string", "optional": True}
            }, "required": ["scenario_id", "label", "kind", "value", "interval", "basis", "source_ids", "as_of"]}},
            "chapters": {"type": "array", "items": {"type": "integer"}}
        }, "required": ["set_id", "mutually_exclusive", "collectively_exhaustive", "resolution_due", "estimates", "chapters"]}},
        "change_reason": {"type": "string"},
        "freeze": {"type": "boolean", "description": "首次无账本先false，按validation补测试/阈值/概率锚点后再true", "optional": True}
    }
}  # type: ignore[attr-defined]
write_decisive_question_findings._tool_meta = {
    "name": "write_decisive_question_findings",
    "description": "提交入选决定性问题的研究结果：区分信号、竞争解释更新、VERIFIED证据，以及估值和仓位动作变化；每个入选问题都必须有结果",
    "parameters": {
        "output_dir": {"type": "string"},
        "findings": {
            "type": "array",
            "minItems": 1,
            "optional": True,
            "description": "每项含question_id/outcome/evidence_observation_ids/attempted_sources/signal_results/explanation_update/decision_update/conclusion/unresolved",
            "items": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "outcome": {"type": "string", "enum": ["RESOLVED", "INCONCLUSIVE", "PUBLIC_INFO_UNAVAILABLE"]},
                    "evidence_observation_ids": {"type": "array", "items": {"type": "string"}},
                    "evidence_calculation_ids": {"type": "array", "items": {"type": "string"}},
                    "attempted_sources": {"type": "array", "items": {"type": "string"}},
                    "signal_results": {"type": "array", "items": {"type": "object", "properties": {
                        "signal_id": {"type": "string"}, "result": {"type": "string"},
                        "supports_explanation_id": {"type": "string"},
                        "evidence_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}}
                    }, "required": ["signal_id", "result", "supports_explanation_id", "evidence_ids"]}},
                    "explanation_update": {"type": "object", "properties": {
                        "favored_explanation_id": {"type": "string"},
                        "confidence_before": {"type": "number"}, "confidence_after": {"type": "number"},
                        "basis": {"type": "string"}
                    }, "required": ["favored_explanation_id", "confidence_before", "confidence_after", "basis"]},
                    "decision_update": {"type": "object", "properties": {
                        "valuation_impact": {"type": "string"}, "position_impact": {"type": "string"},
                        "action": {"type": "string"}, "changed": {"type": "boolean"},
                        "decision_entry_ids": {"type": "array", "items": {"type": "string"}}
                    }, "required": ["valuation_impact", "position_impact", "action", "changed", "decision_entry_ids"]},
                    "conclusion": {"type": "string"},
                    "unresolved": {"type": "array", "items": {"type": "string"}},
                    "inference_audit": {"type": "array", "items": {"type": "object", "properties": {
                        "inference_id": {"type": "string"}, "claim": {"type": "string"},
                        "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
                        "strongest_alternative": {"type": "string"},
                        "discriminating_observation": {"type": "string"},
                        "decision_if_wrong": {"type": "string"}
                    }, "required": ["inference_id", "claim", "supporting_evidence_ids", "strongest_alternative", "discriminating_observation", "decision_if_wrong"]}},
                    "resolution_assessment": {"type": "object", "properties": {
                        "net_support": {"type": "string", "enum": ["EXPLANATION_A", "EXPLANATION_B", "MIXED", "INSUFFICIENT"]},
                        "decision_consistency": {"type": "string"},
                        "premise_resolution": {"type": "array", "items": {"type": "object", "properties": {
                            "premise_key": {"type": "string"}, "plan_value": {},
                            "direction": {"type": "string", "enum": ["SUPPORTS_A", "SUPPORTS_B", "NEUTRAL", "UNKNOWN"]},
                            "evidence_ids": {"type": "array", "items": {"type": "string"}},
                            "assessment": {"type": "string"}
                        }, "required": ["premise_key", "plan_value", "direction", "evidence_ids", "assessment"]}}
                    }, "required": ["net_support", "decision_consistency", "premise_resolution"]}
                },
                "required": ["question_id", "outcome", "evidence_observation_ids", "evidence_calculation_ids", "attempted_sources", "signal_results", "explanation_update", "decision_update", "conclusion", "unresolved"]
            }
        },
        "change_reason": {"type": "string"}
        ,"resume_best_rejected": {"type": "boolean", "description": "为true时从同plan fingerprint的当前最佳失败稿恢复；优先只传finding_patches，也可重传完整findings并全量验证；两者不得同时非空", "optional": True}
        ,"finding_patches": {"type": "array", "description": "按question_id替换指定顶层字段；不能新增问题或改变身份，合并后对全部finding完整重验", "optional": True, "items": {"type": "object", "properties": {
            "question_id": {"type": "string"},
            "outcome": {"type": "string", "enum": ["RESOLVED", "INCONCLUSIVE", "PUBLIC_INFO_UNAVAILABLE"]},
            "evidence_observation_ids": {"type": "array", "items": {"type": "string"}},
            "evidence_calculation_ids": {"type": "array", "items": {"type": "string"}},
            "attempted_sources": {"type": "array", "items": {"type": "string"}},
            "signal_results": {"type": "array", "items": {"type": "object"}},
            "explanation_update": {"type": "object"}, "decision_update": {"type": "object"},
            "conclusion": {"type": "string"}, "unresolved": {"type": "array", "items": {"type": "string"}},
            "inference_audit": {"type": "array", "items": {"type": "object", "properties": {
                "inference_id": {"type": "string"}, "claim": {"type": "string"},
                "supporting_evidence_ids": {"type": "array", "items": {"type": "string"}},
                "strongest_alternative": {"type": "string"},
                "discriminating_observation": {"type": "string"},
                "decision_if_wrong": {"type": "string"}
            }, "required": ["inference_id", "claim", "supporting_evidence_ids", "strongest_alternative", "discriminating_observation", "decision_if_wrong"]}},
            "resolution_assessment": {"type": "object", "properties": {
                "net_support": {"type": "string", "enum": ["EXPLANATION_A", "EXPLANATION_B", "MIXED", "INSUFFICIENT"]},
                "decision_consistency": {"type": "string"},
                "premise_resolution": {"type": "array", "items": {"type": "object"}}
            }, "required": ["net_support", "decision_consistency", "premise_resolution"]}
            ,"premise_resolution": {"type": "array", "description": "按premise_key局部合并现有resolution_assessment.premise_resolution；只提交需修改字段，未提交的plan_value/direction/evidence_ids/assessment及其他前提行全部保留", "items": {"type": "object", "properties": {
                "premise_key": {"type": "string"}, "plan_value": {},
                "direction": {"type": "string", "enum": ["SUPPORTS_A", "SUPPORTS_B", "NEUTRAL", "UNKNOWN"]},
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
                "assessment": {"type": "string"}
            }, "required": ["premise_key"]}}
        }, "required": ["question_id"]}}
    }
}  # type: ignore[attr-defined]
write_insight_ledger._tool_meta = {
    "name": "write_insight_ledger",
    "description": "提交案例校准洞见账本：首要决定性问题、1-3条公司特异洞见、逆向市场预期、价值兑现和最强反方；用于生成精简投资备忘录",
    "parameters": {
        "output_dir": {"type": "string"},
        "archetype": {"type": "string", "enum": ["asset_catalyst", "distressed_survival", "franchise_customer_lockin", "technology_transition", "mature_cash_return", "compounder_reinvestment", "regulated_financial", "operating_transition"]},
        "decisive_question": {"type": "string"},
        "question_basis": {"type": "object", "description": "必须含decisive_question_plan中入选的question_id，并填写anomaly/evidence_ids/why_it_changes_the_decision"},
        "insights": {"type": "array", "description": "1-3项；每项含insight_id/title/claim_id/evidence_ids/anomaly/mechanism/strongest_alternative/discriminating_observation/valuation_impact/action_impact/falsification/company_specific_terms/decision_entry_ids/chapters", "items": {"type": "object"}},
        "reverse_expectations": {"type": "object", "description": "as_of/current_price/method/implied_operating_path/assumptions/valuation_model_ids/conclusion/flip_condition"},
        "value_realization": {"type": "object", "description": "latent_value/controller/access_mechanism/catalyst_required/catalysts/no_catalyst_value/failure_mode/decision_entry_ids"},
        "adversarial_review": {"type": "object", "description": "strongest_case_against/why_it_may_be_right/evidence_ids/unresolved/decision_if_true"},
        "memo": {"type": "object", "description": "executive_decision/valuation_action/monitoring；禁止仅凭价格止损"},
        "change_reason": {"type": "string"}, "freeze": {"type": "boolean", "description": "首次无账本先false；完整洞见和正文锚点通过后再true冻结", "optional": True}
    }
}  # type: ignore[attr-defined]
write_judgment_review._tool_meta = {
    "name": "write_judgment_review",
    "description": "提交独立洞见上限评审；指出差异化洞见、常规内容、脆弱跳跃、缺失信息和决策依赖。仅诊断，不能改变发布门",
    "parameters": {
        "output_dir": {"type": "string"},
        "ceiling_verdict": {"type": "string", "enum": ["INSIGHTFUL", "COMPETENT", "FRAGILE", "NOT_ASSESSABLE"]},
        "verdict_basis": {"type": "string"},
        "distinctive_insight": {"type": "object", "properties": {
            "insight_id": {"type": "string"}, "why_it_matters": {"type": "string"},
            "why_not_obvious": {"type": "string"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "decision_entry_ids": {"type": "array", "items": {"type": "string"}},
            "valuation_model_ids": {"type": "array", "items": {"type": "string"}}
        }, "required": ["insight_id", "why_it_matters", "why_not_obvious", "evidence_ids", "decision_entry_ids", "valuation_model_ids"]},
        "competent_but_conventional": {"type": "array", "items": {"type": "string"}},
        "fragile_leaps": {"type": "array", "items": {"type": "object", "properties": {
            "claim": {"type": "string"}, "why_fragile": {"type": "string"},
            "needed_evidence": {"type": "string"}, "decision_consequence": {"type": "string"}
        }, "required": ["claim", "why_fragile", "needed_evidence", "decision_consequence"]}},
        "competitive_explanation_test": {"type": "object", "properties": {
            "strongest_alternative": {"type": "string"}, "evidence_for_alternative": {"type": "string"},
            "discriminator": {"type": "string"}, "unresolved": {"type": "string"}
        }, "required": ["strongest_alternative", "evidence_for_alternative", "discriminator", "unresolved"]},
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "decision_dependency": {"type": "object", "properties": {
            "without_insight": {"type": "string"}, "changed_values": {"type": "string"},
            "changed_action": {"type": "string"}, "conclusion": {"type": "string"}
        }, "required": ["without_insight", "changed_values", "changed_action", "conclusion"]},
        "dimension_assessments": {"type": "object", "properties": {
            key: {"type": "object", "properties": {
                "state": {"type": "string", "enum": ["strong", "mixed", "weak", "not_assessable"]},
                "basis": {"type": "string"}
            }, "required": ["state", "basis"]}
            for key in ["question_selection", "differentiation", "evidence_discrimination", "valuation_transmission", "action_relevance"]
        }, "required": ["question_selection", "differentiation", "evidence_discrimination", "valuation_transmission", "action_relevance"]},
        "reviewer_limits": {"type": "array", "items": {"type": "string"}}
    }
}  # type: ignore[attr-defined]
plan_judgment_research._tool_meta = {
    "name": "plan_judgment_research",
    "description": "把洞见评审中的脆弱跳跃和缺失信息转成最多3项定向研究任务；每项含来源路线、工具预算、停止规则和可修改章节/账本，禁止全篇扩写",
    "parameters": {
        "output_dir": {"type": "string"},
        "max_tasks_per_run": {"type": "integer", "description": "单轮最多执行任务数，框架硬上限3"}
    }
}  # type: ignore[attr-defined]
begin_judgment_research_task_tool._tool_meta = {
    "name": "begin_judgment_research_task",
    "description": "开始execution_queue中的下一项定向研究；框架随即启用工具预算与章节/账本写入范围保护",
    "parameters": {
        "output_dir": {"type": "string"},
        "task_id": {"type": "string"}
    }
}  # type: ignore[attr-defined]
complete_judgment_research_task_tool._tool_meta = {
    "name": "complete_judgment_research_task",
    "description": "完成当前定向研究任务；机器核验必需工具、来源身份、实际文件变更和decision diff",
    "parameters": {
        "output_dir": {"type": "string"},
        "task_id": {"type": "string", "description": "当前ACTIVE任务ID；省略时框架只会在恰有一个ACTIVE任务时从执行账本安全补全", "optional": True},
        "outcome": {"type": "string", "enum": ["EVIDENCE_FOUND", "PUBLIC_INFO_UNAVAILABLE", "NO_DECISION_CHANGE", "DECISION_CHANGED"], "description": "省略时仅按finding.resolution确定性映射；显式值优先", "optional": True},
        "source_ids": {"type": "array", "items": {"type": "string"}},
        "new_evidence_summary": {"type": "string"},
        "finding": {
            "type": "object",
            "properties": {
                "schema_version": {"type": "string", "enum": ["judgment-research-finding.v1"]},
                "task_id": {"type": "string"},
                "resolution": {"type": "string", "enum": ["SUPPORTED", "CONTRADICTED", "MIXED", "UNRESOLVED", "PUBLIC_INFO_UNAVAILABLE"]},
                "prior_claim": {"type": "string"},
                "evidence_items": {"type": "array", "items": {"type": "object", "properties": {
                    "source_id": {"type": "string"},
                    "source_kind": {"type": "string", "enum": ["primary_filing", "official_data", "independent_dataset", "company_statement", "secondary_research", "market_data", "unknown"]},
                    "directness": {"type": "string", "enum": ["DIRECT", "INDIRECT", "CONTEXT"]},
                    "relation": {"type": "string", "enum": ["supports", "contradicts", "context"]},
                    "fact": {"type": "string"}, "as_of": {"type": "string"}
                }, "required": ["source_id", "source_kind", "directness", "relation", "fact", "as_of"]}},
                "strongest_alternative": {"type": "string"}, "discriminating_result": {"type": "string"},
                "inference": {"type": "string"},
                "applicability_conditions": {"type": "array", "items": {"type": "string"}},
                "confidence_update": {"type": "object", "properties": {
                    "before": {"anyOf": [{"type": "number"}, {"type": "string"}]},
                    "after": {"anyOf": [{"type": "number"}, {"type": "string"}]},
                    "basis": {"type": "string"}
                }, "required": ["before", "after", "basis"]},
                "valuation_impact": {"type": "object", "properties": {
                    "state": {"type": "string", "enum": ["NONE", "CHANGED", "UNCERTAIN"]},
                    "basis": {"type": "string"}, "changes": {"type": "array", "items": {"type": "string"}}
                }, "required": ["state", "basis", "changes"]},
                "action_impact": {"type": "object", "properties": {
                    "state": {"type": "string", "enum": ["NONE", "CHANGED", "UNCERTAIN"]},
                    "basis": {"type": "string"}, "changes": {"type": "array", "items": {"type": "string"}}
                }, "required": ["state", "basis", "changes"]},
                "chapter_update": {"type": "object", "properties": {
                    "needed": {"type": "boolean"}, "chapters": {"type": "array", "items": {"type": "integer"}},
                    "reason": {"type": "string"}
                }, "required": ["needed", "chapters", "reason"]}
            },
            "required": ["schema_version", "task_id", "resolution", "prior_claim", "evidence_items", "strongest_alternative", "discriminating_result", "inference", "applicability_conditions", "confidence_update", "valuation_impact", "action_impact", "chapter_update"]
        }
    }
}  # type: ignore[attr-defined]
finalize_judgment_research_synthesis_tool._tool_meta = {
    "name": "finalize_judgment_research_synthesis",
    "description": "独立复核全部定向研究finding后提交综合结论；机器核验任务覆盖与更新后的judgment_review",
    "parameters": {
        "output_dir": {"type": "string"},
        "integrated_task_ids": {"type": "array", "items": {"type": "string"}},
        "verdict_change": {"type": "object", "description": "before/after/reason"},
        "resolved_gaps": {"type": "array", "items": {"type": "string"}},
        "remaining_gaps": {"type": "array", "items": {"type": "string"}},
        "decision_conclusion": {"type": "string"}
    }
}  # type: ignore[attr-defined]
finalize_judgment_research_review._tool_meta = {
    "name": "finalize_judgment_research_review",
    "description": "原子提交独立judgment_review与研究综合；工具层自动把remaining_gaps同步到missing_information，避免两次提交漂移",
    "parameters": {
        "output_dir": {"type": "string"},
        "judgment_review": {
            "type": "object",
            "description": "完整评审字段：ceiling_verdict、verdict_basis、distinctive_insight、competent_but_conventional、fragile_leaps、competitive_explanation_test、missing_information、decision_dependency、dimension_assessments、reviewer_limits"
        },
        "integrated_task_ids": {"type": "array", "items": {"type": "string"}},
        "verdict_change": {"type": "object", "description": "before/after/reason"},
        "resolved_gaps": {"type": "array", "items": {"type": "string"}},
        "remaining_gaps": {"type": "array", "items": {"type": "string"}},
        "decision_conclusion": {"type": "string"}
    }
}  # type: ignore[attr-defined]
record_research_outcomes._tool_meta = {
    "name": "record_research_outcomes",
    "description": "发布后追加预测结果、触发事件、实际回报和过程错误；新监控计划强制使用Phase 06来源哈希、披露日期和快照绑定契约",
    "parameters": {
        "output_dir": {"type": "string"},
        "events": {
            "type": "array",
            "description": "append-only events；每项需event_id/event_type/observed_at/source_ids",
            "items": {"type": "object"},
        },
    },
}  # type: ignore[attr-defined]
append_strict_monitoring_events._tool_meta = {
    "name": "append_strict_monitoring_events",
    "description": "按Phase 06契约追加带来源哈希和披露日期的监控事件；触发后只生成重估任务，禁止自动交易",
    "parameters": {
        "output_dir": {"type": "string"},
        "events": {
            "type": "array",
            "description": "research-monitoring-event.v2事件；必须绑定report_id、snapshot_fingerprint和source_evidence",
            "items": {"type": "object"},
        },
    },
}  # type: ignore[attr-defined]
read_chapter._tool_meta = {"name": "read_chapter", "description": "读取已写章节内容", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "chapter_index": {"type": "integer", "description": "章序号"}}}  # type: ignore[attr-defined]
audit_chapter._tool_meta = {"name": "audit_chapter", "description": "审计指定章节(S1占位符/E1证据/C2禁止项)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "chapter_index": {"type": "integer", "description": "章序号"}}}  # type: ignore[attr-defined]
assemble_report._tool_meta = {"name": "assemble_report", "description": "组装最终报告(拼接所有章节+来源清单)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "company_name": {"type": "string", "description": "公司全称"}, "ts_code": {"type": "string", "description": "股票代码"}, "validation_only": {"type": "boolean", "optional": True, "description": "仅验证发布前置条件，不创建正式快照或正式报告"}}}  # type: ignore[attr-defined]


def save_comparison(output_dir: str = ".", **kwargs: Any) -> dict[str, Any]:
    """V12.20: 保存结构化跟踪对比数据。

    将本次分析相对上次分析的变化保存为结构化 JSON，
    入库时自动写入 tracking_comparison 表，Web 研究趋势卡片直接读取。

    必须在报告写作完成后、assemble_report 之前调用。

    Args:
        output_dir: 股票输出目录
        **kwargs: 对比字段，支持以下 key：
            previous_node (str): 上一节点描述（如 "2025年报"）
            revenue_yoy (str): 营收同比变化（如 "+8.2%"）
            gross_margin_delta (str): 毛利率变化（如 "+2.3pp"）
            np_yoy (str): 归母净利同比变化
            ocf_yoy (str): 经营现金流同比变化
            key_changes (list): 关键变化列表
            change_classification (str): 归因 (seasonal/cyclical/structural/one_off/accounting)
            thesis_impact (str): 对 thesis 的影响 (维持/强化/弱化/待确认)
            risk_changes (str): 风险变化描述
    """
    path = os.path.join(output_dir, "_comparison.json")
    # Filter only known fields
    valid_keys = {
        "previous_node", "revenue_yoy", "gross_margin_delta",
        "np_yoy", "ocf_yoy", "key_changes",
        "change_classification", "thesis_impact", "risk_changes",
    }
    comparison = {k: v for k, v in kwargs.items() if k in valid_keys}
    if not comparison:
        return {"ok": False, "error": "no valid comparison fields provided"}
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"comparison": comparison}, f, ensure_ascii=False, indent=2)
    return {"ok": True, "path": path, "fields_saved": list(comparison.keys())}


save_comparison._tool_meta = {"name": "save_comparison", "description": "保存结构化跟踪对比数据(相对上次分析的变化)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "previous_node": {"type": "string", "description": "上一节点描述", "optional": True}, "revenue_yoy": {"type": "string", "description": "营收同比变化", "optional": True}, "gross_margin_delta": {"type": "string", "description": "毛利率变化", "optional": True}, "np_yoy": {"type": "string", "description": "归母净利同比", "optional": True}, "ocf_yoy": {"type": "string", "description": "OCF同比", "optional": True}, "key_changes": {"type": "string", "description": "关键变化JSON数组字符串", "optional": True}, "change_classification": {"type": "string", "description": "变化归因(seasonal/cyclical/structural/one_off/accounting)", "optional": True}, "thesis_impact": {"type": "string", "description": "对thesis的影响(维持/强化/弱化/待确认)", "optional": True}, "risk_changes": {"type": "string", "description": "风险变化描述", "optional": True}}}  # type: ignore[attr-defined]
