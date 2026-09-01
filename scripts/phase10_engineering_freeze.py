#!/usr/bin/env python3
"""Assemble a constrained Phase 10 PIT engineering freeze case.

The result is deliberately not a production report or a calibration candidate.
It binds a readable PIT writer draft, its actual source-read attestation, a
separate review artifact, and a ledger that preserves unresolved claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.historical_backtest import CASE_SCHEMA_VERSION, validate_case


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError as exc:
        raise ValueError(f"path must be inside repository: {path}") from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_case(
    *,
    case_id: str,
    experiment_id: str,
    company_code: str,
    cutoff_at: str,
    frozen_at: str,
    report_path: Path,
    attestation_path: Path,
    manifest_path: Path,
    package_root: Path,
    ledger_path: Path,
    review_path: Path,
    writer_id: str,
    writer_context_id: str,
    reviewer_id: str,
    reviewer_context_id: str,
    model_id: str,
    quality_failure: dict[str, Any],
    legacy_attestation_experiment_id: str | None = None,
) -> dict[str, Any]:
    report_path = report_path.resolve()
    attestation_path = attestation_path.resolve()
    manifest_path = manifest_path.resolve()
    package_root = package_root.resolve()
    ledger_path = ledger_path.resolve()
    review_path = review_path.resolve()
    for path in (report_path, attestation_path, manifest_path, ledger_path, review_path):
        if not path.is_file():
            raise ValueError(f"required artifact is missing: {path}")
        _relative(path)
    _relative(package_root)

    attestation = _load_json(attestation_path)
    manifest = _load_json(manifest_path)
    ledger = _load_json(ledger_path)
    claims = ledger.get("claims") if isinstance(ledger.get("claims"), list) else []
    if not claims:
        raise ValueError("ledger must contain frozen claims")
    if ledger.get("contains_realized_outcomes") is not False:
        raise ValueError("engineering freeze ledger cannot contain realized outcomes")
    required_failure_fields = (
        "classifications",
        "economic_impact",
        "missing_facts",
        "prohibited_assumptions",
        "remediation",
        "acceptance_criteria",
    )
    if any(not quality_failure.get(field) for field in required_failure_fields):
        raise ValueError("engineering freeze quality failure is incomplete")
    if not experiment_id.startswith("HBT:"):
        raise ValueError("engineering case must use a canonical HBT: experiment identity")
    attestation_experiment_id = legacy_attestation_experiment_id or experiment_id
    for field, expected in {
        "case_id": case_id,
        "experiment_id": attestation_experiment_id,
        "company_code": company_code,
        "evidence_cutoff": cutoff_at,
    }.items():
        if ledger.get(field) != expected:
            raise ValueError(f"ledger {field} does not match requested case")
    for field, expected in {
        "case_id": case_id,
        "experiment_id": attestation_experiment_id,
        "company_code": company_code,
        "cutoff_at": cutoff_at,
    }.items():
        if attestation.get(field) != expected:
            raise ValueError(f"PIT attestation {field} does not match requested case")
    writer = attestation.get("writer") if isinstance(attestation.get("writer"), dict) else {}
    if writer.get("status") != "PASS":
        raise ValueError("PIT writer did not pass")
    if Path(str(writer.get("report_path") or "")).resolve() != report_path:
        raise ValueError("PIT writer report_path does not match report artifact")
    if writer.get("case_id") != case_id or writer.get("experiment_id") != attestation_experiment_id:
        raise ValueError("PIT writer identity does not match requested case")

    source_ids = {
        str(source_id)
        for claim in claims if isinstance(claim, dict)
        for source_id in (claim.get("source_ids") or [])
    }
    sources_by_id = {
        str(source.get("source_id") or ""): source
        for source in (manifest.get("sources") or []) if isinstance(source, dict)
    }
    if not source_ids or source_ids - set(sources_by_id):
        raise ValueError("ledger references sources not admitted by the manifest")
    writer_source_ids = {str(value) for value in writer.get("source_ids") or []}
    if writer_source_ids != source_ids:
        raise ValueError("PIT writer source ids do not match ledger sources")

    digest = _sha256(report_path)
    variant_id = digest[:16]
    claim_reviews = []
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("ledger claim must be an object")
        disposition = "UNKNOWN_PRESERVED" if claim.get("frozen_disposition") == "UNKNOWN" else "SUPPORTED"
        claim_reviews.append({
            "claim_id": claim.get("claim_id"),
            "disposition": disposition,
            "source_ids": claim.get("source_ids"),
            "notes": ["工程冻结独立复审已确认来源边界和冻结处置。"],
        })
    source_fields = (
        "source_id", "source_version", "source_type", "published_at", "data_as_of", "revision_policy", "admissible",
    )
    sources = [{field: sources_by_id[source_id].get(field) for field in source_fields} for source_id in sorted(source_ids)]
    return {
        "schema_version": CASE_SCHEMA_VERSION,
        "case_id": case_id,
        "experiment_id": experiment_id,
        "company_code": company_code,
        "simulation_cutoff": cutoff_at,
        "report_freeze": {
            "frozen_at": frozen_at,
            "evidence_cutoff": cutoff_at,
            "settlement_locked": True,
            "report_status": "FROZEN_WITH_QUALITY_FAILURE",
            "mode": "PIT_ENGINEERING",
            "freeze_id": "HBTFRZ:" + variant_id,
            "frozen_report": {
                "report_id": "HBTREP:" + case_id.removeprefix("HBTCASE:") + ":PIT_ENGINEERING",
                "variant_id": variant_id,
                "origin": {
                    "kind": "PIT_ENGINEERING",
                    "review_artifact_path": _relative(review_path),
                    **({"legacy_attestation_experiment_id": legacy_attestation_experiment_id} if legacy_attestation_experiment_id else {}),
                    "pit_runner": {
                        "attestation_path": _relative(attestation_path),
                        "source_package_manifest_path": _relative(manifest_path),
                        "package_root": _relative(package_root),
                        "status": "PASS",
                    },
                },
                "artifact_path": _relative(report_path),
                "artifact_sha256": digest,
                "format": "MARKDOWN",
                "writer_id": writer_id,
                "writer_provenance": {
                    "actor_type": "model",
                    "provider": "openai",
                    "model": model_id,
                    "context_id": writer_context_id,
                },
                "writer_status": "QUALITY_FAILURE",
                "claim_ids": [claim.get("claim_id") for claim in claims if isinstance(claim, dict)],
                "section_markers": [
                    "## Point-in-time scope", "## Evidence", "## Business and financial implications", "## Unknowns and monitoring",
                ],
            },
            "independent_review": {
                "review_id": "HBTREV:" + variant_id,
                "reviewed_variant_id": variant_id,
                "reviewer_id": reviewer_id,
                "reviewer_provenance": {
                    "actor_type": "model",
                    "provider": "openai",
                    "model": model_id,
                    "context_id": reviewer_context_id,
                },
                "independence": {
                    "did_not_generate_candidate": True,
                    "no_prior_review_seen": True,
                    "reviewer_context_isolated": True,
                    "generator_identity_disjoint": True,
                },
                "reviewed_report_sha256": digest,
                "status": "FAIL",
                "claim_reviews": claim_reviews,
            },
            "quality_failure": quality_failure,
        },
        "credibility": {
            "model_memory_control": "UNCONTROLLED",
            "backtest_credibility": "EXPLORATORY",
            "assessment_basis": "PIT source reads and review are replayable, but the deployed model has no memory-control attestation.",
            "control_evidence": [],
            "calibration_role": "ENGINEERING_DIAGNOSTIC_ONLY",
        },
        "route": "DUAL",
        "forecast": {
            "horizon_years": 1,
            "terminal_handling": "DUAL_TERMINAL_PATH",
            "cash_flow_basis": "No ordinary-share cash forecast was frozen; all material cash and refinancing claims remain UNKNOWN.",
        },
        "sources": sources,
        "inputs": [],
        "calibration_ledger": {"claims": claims},
        "taxes_fees_fx": {
            "tax_rate": 0.0,
            "transaction_fee_rate": 0.0,
            "dividend_tax_rate": 0.0,
            "base_currency": "CNY",
            "fx_rule": "No investment action or return is frozen in this engineering case.",
        },
        "price_identity": {
            "primary_route": "PRIMARY_ROUTE_UNKNOWN",
            "primary_price_identity": "UNKNOWN",
            "prices": [],
        },
        "status": "FROZEN_WITH_QUALITY_FAILURE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--company-code", required=True)
    parser.add_argument("--cutoff-at", required=True)
    parser.add_argument("--frozen-at", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--writer-id", required=True)
    parser.add_argument("--writer-context-id", required=True)
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--reviewer-context-id", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--legacy-attestation-experiment-id")
    parser.add_argument("--failure-classification", action="append", required=True)
    parser.add_argument("--failure-economic-impact", required=True)
    parser.add_argument("--failure-missing-fact", action="append", required=True)
    parser.add_argument("--failure-prohibited-assumption", action="append", required=True)
    parser.add_argument("--failure-remediation", required=True)
    parser.add_argument("--failure-acceptance-criteria", required=True)
    args = parser.parse_args()
    case = build_case(
        case_id=args.case_id,
        experiment_id=args.experiment_id,
        company_code=args.company_code,
        cutoff_at=args.cutoff_at,
        frozen_at=args.frozen_at,
        report_path=args.report,
        attestation_path=args.attestation,
        manifest_path=args.manifest,
        package_root=args.package_root,
        ledger_path=args.ledger,
        review_path=args.review,
        writer_id=args.writer_id,
        writer_context_id=args.writer_context_id,
        reviewer_id=args.reviewer_id,
        reviewer_context_id=args.reviewer_context_id,
        model_id=args.model_id,
        legacy_attestation_experiment_id=args.legacy_attestation_experiment_id,
        quality_failure={
            "classifications": args.failure_classification,
            "economic_impact": args.failure_economic_impact,
            "missing_facts": args.failure_missing_fact,
            "prohibited_assumptions": args.failure_prohibited_assumption,
            "remediation": args.failure_remediation,
            "acceptance_criteria": args.failure_acceptance_criteria,
        },
    )
    result = validate_case(case, allow_test_fixtures=False)
    if result["invalid_findings"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    expected_quality_failure = (
        case["status"] == "FROZEN_WITH_QUALITY_FAILURE"
        and result["state"] == "INCOMPLETE"
        and "case_frozen_with_quality_failure" in result["incomplete_findings"]
    )
    if result["state"] != "REVIEWABLE" and not expected_quality_failure:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2
    output = args.output.resolve()
    _relative(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": _relative(output),
        "state": result["state"],
        "incomplete_findings": result["incomplete_findings"],
        "freeze_id": case["report_freeze"]["freeze_id"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
