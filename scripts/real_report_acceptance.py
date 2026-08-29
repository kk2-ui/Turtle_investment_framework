#!/usr/bin/env python3
"""Non-compensating acceptance harness for real Turtle reports.

Machine checks can make a report reviewable, never insightful.  Benchmark
approval additionally requires independent reviews and explicit human consent.
The harness reads candidate directories without re-running or mutating their
quality validators; its own artifacts live under a separate acceptance root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "real-report-acceptance.v1"
CONFIG_VERSION = "real-report-acceptance-config.v1"
REVIEW_VERSION = "independent-report-review.v2"
GOLD_VERSION = "gold-report-contract.v1"
PHASE10_PRODUCTION_FREEZE_PHASE = "10-production-freeze"
PHASE10_PRODUCTION_FREEZE_CONFIG_NAME = "phase10_production_freeze_config.json"
MACHINE_STATES = {
    "NOT_ASSESSABLE", "TECHNICALLY_BLOCKED", "READY_FOR_BLIND_REVIEW",
    "REVISION_REQUIRED", "BENCHMARK_CANDIDATE", "BENCHMARK_APPROVED",
}
REVIEW_DIMENSIONS = (
    "decisive_question_quality", "evidence_discrimination", "causal_depth",
    "forward_judgment_quality", "valuation_judgment", "action_coherence",
    "information_efficiency",
)
DIMENSION_STATES = {"STRONG", "MIXED", "WEAK", "NOT_ASSESSABLE"}
CEILING_VERDICTS = {"INSIGHTFUL", "COMPETENT", "FRAGILE", "NOT_ASSESSABLE"}

# These are current-pipeline capabilities, not historical content requirements.
# A legacy report may still be useful to a reviewer, but cannot be called a
# current benchmark until it is regenerated through these contracts.
REQUIRED_MACHINE_GATES: dict[str, tuple[str, set[str]]] = {
    "completion": ("completion_report.json", {"COMPLETE", "COMPLETE_WITH_WARNINGS"}),
    "runtime_manifest": ("run_manifest.json", {"COMPLETED"}),
    "official_evidence": ("official_evidence_validation.json", {"REVIEWABLE", "DECISION_READY", "MONITORING"}),
    "valuation_route": ("valuation_route_validation.json", {"REVIEWABLE", "DECISION_READY", "MONITORING"}),
    "decisive_questions": ("decisive_question_validation.json", {"DECISION_READY", "MONITORING"}),
    "decision_ledger": ("decision_ledger_validation.json", {"DECISION_READY", "MONITORING"}),
    "decision_compiler": ("decision_compiler_validation.json", {"DECISION_READY", "MONITORING"}),
    "claim_evidence": ("claim_evidence_validation.json", {"DECISION_READY", "MONITORING"}),
    "valuation_model": ("valuation_model_validation.json", {"DECISION_READY", "MONITORING"}),
    "decision_reliability": ("decision_reliability_validation.json", {"DECISION_READY", "MONITORING"}),
    "thesis_test": ("thesis_test_validation.json", {"DECISION_READY", "MONITORING"}),
    "insight": ("insight_validation.json", {"DECISION_READY", "MONITORING"}),
    "judgment_review": ("judgment_review_validation.json", {"REVIEWED"}),
    "judgment_synthesis": ("judgment_research_synthesis.json", {"REVIEWED", "NO_ACTION"}),
    "absolute_quality": ("absolute_quality_scorecard.json", {"PASS"}),
}

# A company-judgment release must still be evidence-first and point-in-time
# reviewable.  It deliberately does not fabricate a valuation, a return, or an
# investment action just to satisfy an investment-decision release contract.
CJO_REQUIRED_MACHINE_GATES: dict[str, tuple[str, set[str]]] = {
    "completion": ("completion_report.json", {"COMPLETE", "COMPLETE_WITH_WARNINGS"}),
    "runtime_manifest": ("run_manifest.json", {"COMPLETED"}),
    "official_evidence": ("official_evidence_validation.json", {"REVIEWABLE", "DECISION_READY", "MONITORING"}),
    "financial_driver_bridge": ("financial_driver_bridge_validation.json", {"REVIEWABLE", "DECISION_READY", "MONITORING"}),
    "claim_evidence": ("claim_evidence_validation.json", {"DECISION_READY", "MONITORING"}),
    "thesis_test": ("thesis_test_validation.json", {"DECISION_READY", "MONITORING"}),
    "insight": ("insight_validation.json", {"DECISION_READY", "MONITORING"}),
    "judgment_review": ("judgment_review_validation.json", {"REVIEWED"}),
    "judgment_synthesis": ("judgment_research_synthesis.json", {"REVIEWED", "NO_ACTION"}),
    "absolute_quality": ("absolute_quality_scorecard.json", {"PASS"}),
}
ANALYSIS_PURPOSES = {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else _repo_root() / "config" / "real_report_acceptance.v1.json"
    payload = _load(target)
    if payload.get("schema_version") != CONFIG_VERSION:
        raise ValueError("acceptance config schema mismatch")
    if not isinstance(payload.get("samples"), list) or not payload["samples"]:
        raise ValueError("acceptance samples missing")
    return payload


def build_phase10_production_freeze_config(
    *,
    sample_id: str,
    company_code: str,
    output_dir: str | Path,
    report_period: str,
    archetype: str = "point_in_time_production_freeze",
) -> dict[str, Any]:
    """Build the isolated Phase 10 acceptance registration for one freeze.

    Phase 10 cases must use the ordinary Phase 08 machine gates, but they must
    not amend the frozen Phase 08 candidate set.  The caller supplies the
    fresh production output and stores the resulting baseline under a separate
    acceptance root.
    """
    values = {
        "sample_id": sample_id,
        "company_code": company_code,
        "output_dir": str(output_dir),
        "report_period": report_period,
        "archetype": archetype,
    }
    missing = sorted(name for name, value in values.items() if not str(value or "").strip())
    if missing:
        raise ValueError("phase10 production acceptance requires: " + ", ".join(missing))
    return {
        "schema_version": CONFIG_VERSION,
        "phase": PHASE10_PRODUCTION_FREEZE_PHASE,
        "policy": {
            "minimum_independent_reviews": 2,
            "human_approval_required": True,
            "automatic_ceiling": "READY_FOR_BLIND_REVIEW",
            "no_compensating_score": True,
            "control_sample_hidden_until_rules_frozen": True,
            "rules_frozen": True,
            "forward_judgment_contract_required": True,
        },
        "samples": [{
            "sample_id": str(sample_id).strip(),
            "company_code": str(company_code).strip(),
            "archetype": str(archetype).strip(),
            "role": "historical_production_freeze",
            "output_dir": str(output_dir),
            "report_period": str(report_period).strip(),
            "rules_visible": True,
        }],
    }


def resolve_output_dir(raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else _repo_root() / path


def find_report(output: Path) -> Path | None:
    reports = output / "reports"
    preferred = (
        "最新年报_分析报告_v13.md", "最新_分析报告_v13.md",
        f"{output.name.split('_', 1)[0]}_分析报告_v13.md",
    )
    formal_candidates = [reports / name for name in preferred if (reports / name).is_file()]
    formal_candidates.extend(
        path for path in sorted(reports.glob("*_分析报告_v13.md"))
        if path not in formal_candidates
    ) if reports.is_dir() else None
    # Phase-08 runs are intentionally validation-only. A draft is a legitimate
    # acceptance object, but machine gates still decide whether it is reviewable;
    # locating it must never imply publication or completion.
    drafts = reports / "drafts"
    draft_candidates = sorted(drafts.glob("*_分析报告_v13_draft.md")) if drafts.is_dir() else []
    latest_draft = max(draft_candidates, key=lambda path: path.stat().st_mtime) if draft_candidates else None
    latest_formal = max(formal_candidates, key=lambda path: path.stat().st_mtime) if formal_candidates else None
    completion = _load(output / "completion_report.json")
    run_manifest = _load(output / "run_manifest.json")
    publication = run_manifest.get("publication") if isinstance(run_manifest.get("publication"), dict) else {}
    validated_not_published = (
        run_manifest.get("status") == "COMPLETED"
        and publication.get("validation_only") is True
        and publication.get("status") == "VALIDATED_NOT_PUBLISHED"
    )
    if (
        latest_draft is not None
        and (
            validated_not_published
            or (
                str(completion.get("status") or "").upper() in {"COMPLETE", "COMPLETE_WITH_WARNINGS"}
                and (latest_formal is None or latest_draft.stat().st_mtime >= latest_formal.stat().st_mtime)
            )
        )
    ):
        return latest_draft
    return latest_formal or latest_draft


def find_technical_report(report: Path | None) -> Path | None:
    if report is None:
        return None
    name = report.name
    if name.endswith("_draft.md"):
        candidate = report.with_name(name.replace("_draft.md", "_technical_draft.md"))
    else:
        candidate = report.with_name(name.replace(".md", "_technical.md"))
    return candidate if candidate.is_file() else None


def _report_bundle_hash(report: Path, technical: Path | None) -> str:
    if technical is None:
        return _file_hash(report)
    return _hash({
        "memo_sha256": _file_hash(report),
        "technical_sha256": _file_hash(technical),
    })


def resolve_report_variant(output: Path) -> dict[str, Any]:
    """Resolve the current pipeline report and Phase 08 variant identity."""
    report = find_report(output)
    technical = find_technical_report(report)
    report_sha256 = _report_bundle_hash(report, technical) if report else ""
    return {
        "report": report,
        "technical_report": technical,
        "report_sha256": report_sha256,
        "variant_id": report_sha256[:16] if report_sha256 else "",
        "hard_gates": evaluate_machine_gates(output),
    }


def summarize_candidate_provenance(output: Path) -> dict[str, Any]:
    """Return known generator identities without pretending authorship is exhaustive."""
    identities: set[str] = set()
    manifests: list[dict[str, str]] = []
    manifest_paths: list[Path] = []
    current = output / "run_manifest.json"
    if current.is_file():
        manifest_paths.append(current)
    archive = output / "run_manifests"
    if archive.is_dir():
        manifest_paths.extend(sorted(archive.glob("*.json")))
    for path in manifest_paths:
        payload = _load(path)
        calls = payload.get("llm_calls") if isinstance(payload.get("llm_calls"), list) else []
        call_identities: set[str] = set()
        for call in calls:
            if not isinstance(call, dict):
                continue
            provider = str(call.get("provider") or "").strip().lower()
            model = str(call.get("model") or "").strip().lower()
            if provider and model:
                call_identities.add(f"{provider}:{model}")
        if call_identities:
            identities.update(call_identities)
            manifests.append({"path": path.name, "sha256": _file_hash(path)})
    return {
        "known_generator_identities": sorted(identities),
        "source_manifest_count": len(manifests),
        "source_manifest_set_sha256": _hash(manifests) if manifests else None,
        "coverage": "RECORDED_PIPELINE_ONLY",
        "exhaustive_authorship_claim": False,
    }


def _blind_packet_text(item: dict[str, Any]) -> str:
    report_path = Path(str(item.get("report_path") or ""))
    content = report_path.read_text(encoding="utf-8")
    technical_path = Path(str(item.get("technical_report_path") or ""))
    if technical_path.is_file():
        content += "\n\n---\n\n# 完整技术附录\n\n" + technical_path.read_text(encoding="utf-8")
    content = re.sub(r"(?im)^>.*(?:生成|版本|run[_ -]?id).*$", "", content)
    return (
        "<!-- Phase08 blind packet: candidate path/version intentionally hidden -->\n"
        f"<!-- variant_id={item['variant_id']} -->\n\n{content}"
    )


def _observed_state(payload: dict[str, Any]) -> str:
    for key in ("state", "status", "hard_contract_status"):
        value = str(payload.get(key) or "").upper()
        if value:
            return value
    return "MISSING"


def _analysis_purpose(output: Path) -> tuple[str, bool]:
    contract = _load(output / "analysis_contract.json")
    purpose = str(contract.get("analysis_purpose") or "INVESTMENT_DECISION")
    return purpose, purpose in ANALYSIS_PURPOSES


def evaluate_machine_gates(
    output: Path, *, require_forward_judgment_contract: bool = False,
) -> dict[str, Any]:
    gates: dict[str, Any] = {}
    blocking: list[str] = []
    analysis_purpose, purpose_valid = _analysis_purpose(output)
    required_gates = (
        CJO_REQUIRED_MACHINE_GATES
        if analysis_purpose == "COMPANY_JUDGMENT_ONLY"
        else REQUIRED_MACHINE_GATES
    )
    if not purpose_valid:
        blocking.append("analysis_purpose:INVALID")
        gates["analysis_purpose"] = {
            "file": "analysis_contract.json",
            "observed": analysis_purpose,
            "accepted": sorted(ANALYSIS_PURPOSES),
            "passed": False,
        }
    for gate_id, (filename, accepted) in required_gates.items():
        path = output / filename
        payload = _load(path)
        observed = _observed_state(payload) if payload else "MISSING"
        passed = observed in accepted
        gates[gate_id] = {
            "file": filename,
            "observed": observed,
            "accepted": sorted(accepted),
            "passed": passed,
        }
        if not passed:
            blocking.append(f"{gate_id}:{observed}")
        if analysis_purpose == "COMPANY_JUDGMENT_ONLY" and gate_id in {
            "financial_driver_bridge", "thesis_test",
        }:
            declared_purpose = str(payload.get("analysis_purpose") or "MISSING")
            purpose_passed = declared_purpose == analysis_purpose
            gates[gate_id]["analysis_purpose"] = declared_purpose
            gates[gate_id]["analysis_purpose_passed"] = purpose_passed
            if not purpose_passed:
                blocking.append(f"{gate_id}:analysis_purpose:{declared_purpose}")
    if require_forward_judgment_contract:
        thesis_validation = _load(output / "thesis_test_validation.json")
        observed = str(thesis_validation.get("forward_judgment_state") or "MISSING").upper()
        passed = observed == "DECISION_READY"
        gates["forward_judgment_contract"] = {
            "file": "thesis_test_validation.json",
            "observed": observed,
            "accepted": ["DECISION_READY"],
            "passed": passed,
        }
        if not passed:
            blocking.append(f"forward_judgment_contract:{observed}")
    completion = _load(output / "completion_report.json")
    completion_findings = list(completion.get("blocking_findings") or [])
    return {
        "passed": not blocking,
        "analysis_purpose": analysis_purpose,
        "gates": gates,
        "blocking": blocking,
        "completion_findings": completion_findings[:30],
    }


def summarize_research_execution(output: Path) -> dict[str, Any]:
    payload = _load(output / "research_execution.json")
    chapters = payload.get("chapters") if isinstance(payload.get("chapters"), dict) else {}
    tool_counts: Counter[str] = Counter()
    fiscal_years: set[int] = set()
    section_reads: Counter[str] = Counter()
    enforced_chapters = 0
    missing_sections: list[str] = []
    for chapter_id, entry in chapters.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("enforced"):
            enforced_chapters += 1
        for tool, count in (entry.get("tool_counts") or {}).items():
            try:
                tool_counts[str(tool)] += int(count or 0)
            except (TypeError, ValueError):
                continue
        for year in entry.get("fiscal_years") or []:
            try:
                fiscal_years.add(int(year))
            except (TypeError, ValueError):
                pass
        for section in entry.get("sections") or entry.get("read_sections") or []:
            section_reads[str(section)] += 1
        for section in entry.get("missing_sections") or []:
            missing_sections.append(f"Ch{chapter_id}:{section}")
    return {
        "status": "ENFORCED" if payload.get("enforced") else "RECORDED" if chapters else "MISSING",
        "chapter_records": len(chapters),
        "enforced_chapters": enforced_chapters,
        "fiscal_years": sorted(fiscal_years),
        "tool_counts": dict(sorted(tool_counts.items())),
        "section_reads": dict(sorted(section_reads.items())),
        "missing_sections": sorted(set(missing_sections)),
        "two_fiscal_years_observed": len(fiscal_years) >= 2,
        "primary_read_observed": int(tool_counts.get("read_section", 0)) > 0,
        "web_fetch_observed": int(tool_counts.get("web_fetch", 0)) > 0,
    }


def summarize_insight_ceiling(output: Path) -> dict[str, Any]:
    validation = _load(output / "judgment_review_validation.json")
    review = _load(output / "judgment_review.json")
    fragile = review.get("fragile_leaps") if isinstance(review.get("fragile_leaps"), list) else []
    dimensions = review.get("dimension_assessments") if isinstance(review.get("dimension_assessments"), dict) else {}
    return {
        "review_state": str(validation.get("state") or "NOT_ASSESSABLE"),
        "ceiling_verdict": str(validation.get("ceiling_verdict") or review.get("ceiling_verdict") or "NOT_ASSESSABLE"),
        "fragile_leap_count": len(fragile),
        "dimension_states": {
            name: str(item.get("state") or "not_assessable")
            for name, item in dimensions.items() if isinstance(item, dict)
        },
        "missing_information_count": len(review.get("missing_information") or []),
    }


def validate_independent_review(
    payload: dict[str, Any], sample_id: str, expected_variant_id: str = "",
    *, expected_packet_sha256: str = "",
    known_generator_identities: set[str] | None = None,
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if payload.get("schema_version") != REVIEW_VERSION:
        invalid.append("schema_version_invalid")
    if str(payload.get("sample_id") or "") != sample_id:
        invalid.append("sample_id_mismatch")
    if expected_variant_id and str(payload.get("variant_id") or "") != expected_variant_id:
        invalid.append("variant_id_mismatch")
    for key in ("variant_id", "reviewer_id", "submitted_at"):
        if not str(payload.get(key) or "").strip():
            incomplete.append(key + "_missing")
    independence = payload.get("independence") if isinstance(payload.get("independence"), dict) else {}
    for key in (
        "did_not_generate_candidate", "variant_label_blinded", "no_prior_review_seen",
        "reviewer_context_isolated", "generator_identity_disjoint",
    ):
        if independence.get(key) is not True:
            invalid.append("independence:" + key)
    provenance = payload.get("reviewer_provenance") if isinstance(payload.get("reviewer_provenance"), dict) else {}
    actor_type = str(provenance.get("actor_type") or "")
    if actor_type not in {"human", "model", "hybrid"}:
        invalid.append("reviewer_provenance:actor_type_invalid")
    context_id = str(provenance.get("context_id") or "").strip()
    if not context_id:
        incomplete.append("reviewer_provenance:context_id_missing")
    packet_sha256 = str(provenance.get("reviewed_packet_sha256") or "")
    if expected_packet_sha256 and packet_sha256 != expected_packet_sha256:
        invalid.append("reviewed_packet_sha256_mismatch")
    reviewer_identity = ""
    if actor_type in {"model", "hybrid"}:
        provider = str(provenance.get("provider") or "").strip().lower()
        model = str(provenance.get("model") or "").strip().lower()
        if not provider or not model:
            incomplete.append("reviewer_provenance:model_identity_missing")
        else:
            reviewer_identity = f"{provider}:{model}"
            if reviewer_identity in (known_generator_identities or set()):
                invalid.append("reviewer_generator_identity_overlap")
    dimensions = payload.get("dimensions") if isinstance(payload.get("dimensions"), dict) else {}
    for name in REVIEW_DIMENSIONS:
        item = dimensions.get(name) if isinstance(dimensions.get(name), dict) else {}
        if item.get("state") not in DIMENSION_STATES:
            invalid.append(name + ":state_invalid")
        if len(str(item.get("basis") or "").strip()) < 30:
            incomplete.append(name + ":basis_too_thin")
        if not item.get("report_locations"):
            incomplete.append(name + ":locations_missing")
    if payload.get("ceiling_verdict") not in CEILING_VERDICTS:
        invalid.append("ceiling_verdict_invalid")
    fatal_findings = payload.get("fatal_findings")
    if not isinstance(fatal_findings, list):
        invalid.append("fatal_findings_not_array")
    elif any(not isinstance(item, str) or not item.strip() for item in fatal_findings):
        invalid.append("fatal_findings_item_invalid")
    reviewer_limits = payload.get("reviewer_limits")
    if not reviewer_limits:
        incomplete.append("reviewer_limits_missing")
    elif not isinstance(reviewer_limits, list) or any(
        not isinstance(item, str) or not item.strip() for item in reviewer_limits
    ):
        invalid.append("reviewer_limits_item_invalid")
    return {
        "status": "INVALID" if invalid else "INCOMPLETE" if incomplete else "VALID",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "independence_assurance": (
            "VERIFIED_ARTIFACT_AND_DECLARED_PROCESS"
            if not invalid and not incomplete else "NOT_ESTABLISHED"
        ),
        "review_context_id": context_id,
        "reviewer_model_identity": reviewer_identity,
    }


def load_reviews(
    review_root: Path, sample_id: str, variant_id: str = "", *,
    expected_packet_sha256: str = "", known_generator_identities: set[str] | None = None,
) -> list[dict[str, Any]]:
    directory = review_root / sample_id
    result: list[dict[str, Any]] = []
    if not directory.is_dir():
        return result
    reviewers: set[str] = set()
    contexts: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        payload = _load(path)
        validation = validate_independent_review(
            payload, sample_id, variant_id,
            expected_packet_sha256=expected_packet_sha256,
            known_generator_identities=known_generator_identities,
        )
        reviewer = str(payload.get("reviewer_id") or "")
        context_id = str(validation.get("review_context_id") or "")
        duplicate = (reviewer in reviewers if reviewer else False) or (
            context_id in contexts if context_id else False
        )
        if validation["status"] == "VALID" and reviewer:
            reviewers.add(reviewer)
            contexts.add(context_id)
        result.append({
            "path": str(path), "reviewer_id": reviewer,
            "ceiling_verdict": payload.get("ceiling_verdict"),
            "fatal_findings": list(payload.get("fatal_findings") or []),
            "duplicate_reviewer": duplicate,
            "validation": validation,
        })
    return result


def validate_gold_contract(
    path: Path,
    sample_id: str,
    *,
    expected_variant_id: str = "",
    expected_report_sha256: str = "",
    valid_reviewer_ids: set[str] | None = None,
) -> dict[str, Any]:
    payload = _load(path)
    if not payload:
        return {"status": "MISSING", "approved": False}
    core = deepcopy(payload)
    recorded = str(core.pop("fingerprint", ""))
    invalid = []
    if payload.get("schema_version") != GOLD_VERSION:
        invalid.append("schema_version_invalid")
    if payload.get("sample_id") != sample_id:
        invalid.append("sample_id_mismatch")
    if expected_variant_id and payload.get("variant_id") != expected_variant_id:
        invalid.append("variant_id_mismatch")
    if expected_report_sha256 and payload.get("report_sha256") != expected_report_sha256:
        invalid.append("report_sha256_mismatch")
    review_ids = {str(value) for value in payload.get("review_ids") or [] if str(value)}
    if valid_reviewer_ids is not None and (
        len(review_ids) < 2 or not review_ids.issubset(valid_reviewer_ids)
    ):
        invalid.append("review_ids_not_bound_to_current_valid_reviews")
    if recorded != _hash(core):
        invalid.append("fingerprint_mismatch")
    approval = payload.get("human_approval") if isinstance(payload.get("human_approval"), dict) else {}
    approved = approval.get("approved") is True and bool(approval.get("approved_by")) and bool(approval.get("approved_at"))
    return {"status": "INVALID" if invalid else "VALID", "approved": approved, "invalid_findings": invalid}


def evaluate_sample(
    sample: dict[str, Any], review_root: Path, gold_root: Path, policy: dict[str, Any]
) -> dict[str, Any]:
    output = resolve_output_dir(str(sample.get("output_dir") or ""))
    report = find_report(output)
    technical_report = find_technical_report(report)
    report_sha256 = _report_bundle_hash(report, technical_report) if report else ""
    variant_id = report_sha256[:16] if report_sha256 else ""
    provenance = summarize_candidate_provenance(output)
    packet_item = {
        "report_path": str(report) if report else None,
        "technical_report_path": str(technical_report) if technical_report else None,
        "variant_id": variant_id,
    }
    packet_sha256 = hashlib.sha256(_blind_packet_text(packet_item).encode("utf-8")).hexdigest() if report else ""
    hard = evaluate_machine_gates(
        output,
        require_forward_judgment_contract=bool(
            policy.get("forward_judgment_contract_required")
        ),
    )
    research = summarize_research_execution(output)
    ceiling = summarize_insight_ceiling(output)
    reviews = load_reviews(
        review_root, str(sample["sample_id"]), variant_id,
        expected_packet_sha256=packet_sha256,
        known_generator_identities=set(provenance["known_generator_identities"]),
    )
    valid_reviews = [item for item in reviews if item["validation"]["status"] == "VALID" and not item["duplicate_reviewer"]]
    minimum_reviews = int(policy["minimum_independent_reviews"])
    review_verdict_counts = Counter(str(item.get("ceiling_verdict") or "") for item in valid_reviews)
    fatal_review_findings = [
        {"reviewer_id": str(item["reviewer_id"]), "finding": finding}
        for item in valid_reviews for finding in item["fatal_findings"]
    ]
    review_failed = (
        len(valid_reviews) >= minimum_reviews
        and (
            bool(fatal_review_findings)
            or any(item["ceiling_verdict"] in {"FRAGILE", "NOT_ASSESSABLE"} for item in valid_reviews)
        )
    )
    review_ready = (
        len(valid_reviews) >= minimum_reviews
        and not any(item["fatal_findings"] for item in valid_reviews)
        and any(item["ceiling_verdict"] == "INSIGHTFUL" for item in valid_reviews)
        and not any(item["ceiling_verdict"] in {"FRAGILE", "NOT_ASSESSABLE"} for item in valid_reviews)
    )
    gold = validate_gold_contract(
        gold_root / f"{sample['sample_id']}.json",
        str(sample["sample_id"]),
        expected_variant_id=variant_id,
        expected_report_sha256=report_sha256,
        valid_reviewer_ids={str(item["reviewer_id"]) for item in valid_reviews},
    )
    if report is None:
        status = "NOT_ASSESSABLE"
    elif not hard["passed"]:
        status = "TECHNICALLY_BLOCKED"
    elif review_failed:
        status = "REVISION_REQUIRED"
    elif review_ready:
        status = "BENCHMARK_CANDIDATE"
    else:
        status = "READY_FOR_BLIND_REVIEW"
    if status == "BENCHMARK_CANDIDATE" and gold.get("status") == "VALID" and gold.get("approved"):
        status = "BENCHMARK_APPROVED"
    priorities = list(hard["blocking"])
    if research["status"] != "ENFORCED":
        priorities.append("research_execution_not_enforced")
    if not research["two_fiscal_years_observed"]:
        priorities.append("two_fiscal_year_reads_not_observed")
    if not research["primary_read_observed"]:
        priorities.append("read_section_not_observed")
    if ceiling["ceiling_verdict"] != "INSIGHTFUL":
        priorities.append("insight_ceiling:" + ceiling["ceiling_verdict"])
    if review_failed:
        priorities.append("independent_review:revision_required")
    absolute = _load(output / "absolute_quality_scorecard.json")
    for idx in absolute.get("review_chapters") or []:
        priorities.append(f"chapter_review_priority:Ch{idx}")
    return {
        "sample_id": sample["sample_id"],
        "company_code": sample["company_code"],
        "archetype": sample["archetype"],
        "role": sample["role"],
        "output_dir": str(output),
        "report_path": str(report) if report else None,
        "technical_report_path": str(technical_report) if technical_report else None,
        "report_sha256": report_sha256 or None,
        "variant_id": variant_id,
        "blind_packet_sha256": packet_sha256 or None,
        "candidate_provenance": provenance,
        "machine_status": status,
        "hard_gates": hard,
        "research_execution": research,
        "insight_ceiling": ceiling,
        "independent_reviews": reviews,
        "independent_review_outcome": {
            "valid_review_count": len(valid_reviews),
            "minimum_required": minimum_reviews,
            "verdict_counts": dict(sorted(review_verdict_counts.items())),
            "fatal_finding_count": len(fatal_review_findings),
            "fatal_findings": fatal_review_findings,
            "revision_required": review_failed,
        },
        "gold_contract": gold,
        "review_priority": list(dict.fromkeys(priorities)),
    }


def _evaluate_config(
    config: dict[str, Any],
    *,
    acceptance_root: str | Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    root = Path(acceptance_root) if acceptance_root else _repo_root() / "output" / ".acceptance" / "phase08"
    review_root = root / "reviews"
    gold_root = root / "gold_contracts"
    holdout_enabled = bool(config["policy"].get("control_sample_hidden_until_rules_frozen"))
    rules_frozen = bool(config["policy"].get("rules_frozen"))
    visible_samples = [
        sample for sample in config["samples"]
        if not (holdout_enabled and not rules_frozen and sample.get("rules_visible") is False)
    ]
    samples = [
        evaluate_sample(sample, review_root, gold_root, config["policy"])
        for sample in visible_samples
    ]
    counts = Counter(item["machine_status"] for item in samples)
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "config_fingerprint": _hash(config),
        "policy": config["policy"],
        "summary": {
            "sample_count": len(samples),
            "registered_sample_count": len(config["samples"]),
            "held_out_count": len(config["samples"]) - len(samples),
            "rules_frozen": rules_frozen,
            "status_counts": dict(sorted(counts.items())),
            "benchmark_approved_count": counts.get("BENCHMARK_APPROVED", 0),
            "automatic_quality_claim_forbidden": True,
        },
        "samples": samples,
    }
    if persist:
        root.mkdir(parents=True, exist_ok=True)
        (root / "acceptance_baseline.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        (root / "acceptance_baseline.md").write_text(render_markdown(result), encoding="utf-8")
        write_blind_packets(result, root / "blind_packets")
    return result


def evaluate_acceptance(
    config_path: str | Path | None = None,
    *,
    acceptance_root: str | Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    return _evaluate_config(
        load_config(config_path),
        acceptance_root=acceptance_root,
        persist=persist,
    )


def evaluate_phase10_production_freeze_acceptance(
    *,
    sample_id: str,
    company_code: str,
    output_dir: str | Path,
    report_period: str,
    acceptance_root: str | Path,
    archetype: str = "point_in_time_production_freeze",
    persist: bool = True,
) -> dict[str, Any]:
    """Evaluate one PIT production freeze under the unmodified Phase 08 gates."""
    root = Path(acceptance_root)
    config = build_phase10_production_freeze_config(
        sample_id=sample_id,
        company_code=company_code,
        output_dir=output_dir,
        report_period=report_period,
        archetype=archetype,
    )
    if persist:
        root.mkdir(parents=True, exist_ok=True)
        (root / PHASE10_PRODUCTION_FREEZE_CONFIG_NAME).write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return _evaluate_config(config, acceptance_root=root, persist=persist)


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Phase 08 真实报告机器验收基线", "",
        "> 无总分。机器最多判定 READY_FOR_BLIND_REVIEW，不能自动宣称洞见优秀。", "",
        "| 样本 | 角色 | 机器状态 | 硬门 | 研究执行 | 洞见上限 | 独立有效评审 |", "|---|---|---|---|---|---|---:|",
    ]
    for item in result["samples"]:
        valid_reviews = sum(
            review["validation"]["status"] == "VALID" and not review["duplicate_reviewer"]
            for review in item["independent_reviews"]
        )
        lines.append(
            f"| {item['sample_id']} | {item['role']} | **{item['machine_status']}** | "
            f"{'PASS' if item['hard_gates']['passed'] else 'FAIL'} | "
            f"{item['research_execution']['status']} | {item['insight_ceiling']['ceiling_verdict']} | {valid_reviews} |"
        )
    lines.extend(["", "## 复核优先级", ""])
    for item in result["samples"]:
        lines.append(f"### {item['sample_id']}")
        lines.append("")
        lines.extend(f"- {finding}" for finding in item["review_priority"][:30])
        if not item["review_priority"]:
            lines.append("- 无机器阻断；等待独立盲评。")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_blind_packets(result: dict[str, Any], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    packet_index: list[dict[str, str]] = []
    for item in result["samples"]:
        if item.get("machine_status") not in {
            "READY_FOR_BLIND_REVIEW", "REVISION_REQUIRED",
            "BENCHMARK_CANDIDATE", "BENCHMARK_APPROVED"
        }:
            continue
        report_path = Path(str(item.get("report_path") or ""))
        if not report_path.is_file():
            continue
        packet_text = _blind_packet_text(item)
        (directory / f"{item['variant_id']}.md").write_text(packet_text, encoding="utf-8")
        template = {
            "schema_version": REVIEW_VERSION,
            "review_contract": {
                "dimension_state_allowed_values": sorted(DIMENSION_STATES),
                "ceiling_verdict_allowed_values": sorted(CEILING_VERDICTS),
                "fatal_findings_format": "array of non-empty strings; include report location in each string",
                "reviewer_limits_format": "array of non-empty strings",
                "instruction": (
                    "Use only the exact enum values above. Do not submit PASS/FAIL, "
                    "free-form verdicts, or object-valued fatal findings. For "
                    "causal_depth, require a bounded industry-future thesis that selects "
                    "the most likely regime, traces the profit-pool change into this "
                    "company's exposure and adaptation, and reaches normal economics or "
                    "permanent loss; a trend inventory is WEAK. For "
                    "forward_judgment_quality, decide whether the report actually selects "
                    "a more likely 3/5-year path, discriminates the strongest alternative, "
                    "and transmits its frozen judgments into earnings, owner cash, value, "
                    "and expected return; a sensitivity table alone is WEAK."
                ),
            },
            "sample_id": item["sample_id"],
            "variant_id": item["variant_id"],
            "reviewer_id": "",
            "reviewer_provenance": {
                "actor_type": "model",
                "provider": "",
                "model": "",
                "context_id": "",
                "reviewed_packet_sha256": item["blind_packet_sha256"],
            },
            "independence": {
                "did_not_generate_candidate": True,
                "variant_label_blinded": True,
                "no_prior_review_seen": True,
                "reviewer_context_isolated": True,
                "generator_identity_disjoint": True,
            },
            "dimensions": {
                name: {"state": "NOT_ASSESSABLE", "basis": "", "report_locations": []}
                for name in REVIEW_DIMENSIONS
            },
            "ceiling_verdict": "NOT_ASSESSABLE",
            "fatal_findings": [],
            "reviewer_limits": [],
            "submitted_at": "",
        }
        (directory / f"{item['variant_id']}.review_template.json").write_text(
            json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        packet_index.append({
            "sample_id": str(item["sample_id"]),
            "variant_id": str(item["variant_id"]),
            "report_sha256": str(item["report_sha256"]),
            "blind_packet_sha256": str(item["blind_packet_sha256"]),
            "known_generator_identities": list(item["candidate_provenance"]["known_generator_identities"]),
            "packet": f"{item['variant_id']}.md",
            "review_template": f"{item['variant_id']}.review_template.json",
        })
    (directory / "blind_packet_index.json").write_text(
        json.dumps({
            "schema_version": "blind-packet-index.v1",
            "generated_at": result["generated_at"],
            "packets": packet_index,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 08 real report acceptance")
    parser.add_argument("--config", default="")
    parser.add_argument("--acceptance-root", default="")
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args(argv)
    result = evaluate_acceptance(
        args.config or None,
        acceptance_root=args.acceptance_root or None,
        persist=not args.no_persist,
    )
    print(json.dumps(result["summary"], ensure_ascii=False))
    return 0 if result["summary"]["benchmark_approved_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
