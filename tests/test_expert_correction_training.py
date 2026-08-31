from __future__ import annotations

import json
from pathlib import Path

from scripts.expert_correction_training import (
    compile_training_memory,
    validate_teacher_package,
)


ROOT = Path(__file__).resolve().parents[1]


def _package(tmp_path: Path) -> dict:
    report = tmp_path / "report.md"
    review = tmp_path / "review.md"
    principle = tmp_path / "principle.md"
    for path in (report, review, principle):
        path.write_text("reviewed teacher material\n", encoding="utf-8")
    return {
        "schema_version": "expert-correction-teacher-package.v1",
        "package_id": "TEACHER:TEST:V1",
        "case_identity": {
            "company_id": "HK:00001",
            "company_name": "教师公司",
            "case_cutoff_at": "2026-08-11T23:59:59+08:00",
            "teaching_identity": "RESULT_KNOWN_EXPERT_CORRECTED",
            "outcome_access": "RESULT_KNOWN",
        },
        "source_artifacts": [
            {
                "artifact_id": "SOURCE:REPORT",
                "ref": str(report),
                "role": "TARGET_REPORT",
                "review_state": "ACCEPT_WITH_DATA_LIMITED_TEACHING_PROVENANCE",
                "teaching_use": "Final target form, not target-company evidence.",
            },
            {
                "artifact_id": "SOURCE:REVIEW",
                "ref": str(review),
                "role": "MATERIAL_REVIEW",
                "review_state": "ACCEPTED_TEACHING_PROVENANCE",
                "teaching_use": "Accepted correction provenance.",
            },
            {
                "artifact_id": "SOURCE:PRINCIPLE",
                "ref": str(principle),
                "role": "PRINCIPLE_SOURCE",
                "review_state": "ACCEPTED_TEACHING_PROVENANCE",
                "teaching_use": "Conditional principle source.",
            },
        ],
        "correction_events": [
            {
                "event_id": "ECORR:ROUTE_IDENTITY",
                "accepted_source_artifact_ids": ["SOURCE:REVIEW"],
                "before_error_pattern": "A calculated conditional route was presented as an action route.",
                "root_cause_classes": ["MODEL", "REASONING", "WRITING"],
                "economic_object": "route identity",
                "responsibility_boundary": "business value versus future market realization",
                "error_mechanism": "Arithmetic closure was mistaken for economic evidence.",
                "economic_impact": "The investor could pay for an unproved realization path.",
                "prohibited_assumptions": ["A calculated route is automatically executable."],
                "correction": {
                    "best_current_judgment": "Keep an unsupported realization route conditional.",
                    "required_company_evidence": ["Independent realization evidence"],
                    "investor_consequence": "Do not promote the route to an action price.",
                    "uncertainty_treatment": "Preserve the route as a scenario.",
                    "countercondition": "A contractual or repeated cash realization path can support promotion.",
                    "reversal_observation": "Observed realization closes the route-specific evidence gap.",
                },
                "transfer": {
                    "portable_rule": "A complete calculation does not establish the economic identity of its terminal assumption.",
                    "applicable_when": "A route depends on future market recognition or another unproved realization event.",
                    "not_applicable_when": "The terminal receipt is contractually fixed or already realized within the responsibility boundary.",
                    "next_case_probe": "Separate operating value, shareholder cash and market realization before choosing a route.",
                },
                "decision_surfaces": ["VALUE_ROUTE", "PRICE_IDENTITY"],
            }
        ],
        "conditional_principles": [
            {
                "principle_id": "PRINCIPLE:VALUE_COMPONENTS",
                "title": "Separate current earning power from unproved growth",
                "source_artifact_id": "SOURCE:PRINCIPLE",
                "principle_statement": "Growth deserves value only when incremental economics and owner realization are supportable.",
                "economic_object": "earning power and growth value",
                "applicable_when": "The thesis relies on expansion, new cohorts or retained capital.",
                "mechanism": "Expansion creates owner value only after customer adoption, unit economics and cash absorption support an adequate incremental return.",
                "target_company_evidence": ["Customer adoption", "Incremental unit economics", "Cash absorption"],
                "common_misuse": "Treating revenue growth or project completion as proven owner value.",
                "counterconditions": ["A regulated pass-through can make a different evidence chain decisive."],
                "downstream_use": "Keep unproved growth outside base normal earnings and preserve it as a conditional component.",
                "disconfirming_observation": "Repeated mature cohorts earn and distribute adequate incremental cash.",
                "derived_from_event_ids": ["ECORR:ROUTE_IDENTITY"],
            }
        ],
        "cutoff_feedback_design": {
            "status": "PREREGISTERED_NO_OUTCOME_VALUES",
            "target_identity_rule": "Use a different company or later unseen cutoff.",
            "outcome_source_policy": "Use predeclared official filings after the clock opens.",
            "forbidden_outcome_proxies": ["Share-price movement", "Retrospective management narrative"],
            "feedback_clocks": [
                {
                    "clock_id": "CLOCK:OPERATING",
                    "horizon": "OPERATING_ADAPTATION",
                    "episode_claims": ["BUSINESS_POSITION_AND_ADAPTATION", "OWNER_CASH"],
                    "diagnostic_observation": "Customer adoption, unit economics and cash absorption move together.",
                    "supports_rule": "The frozen conditional treatment avoided premature promotion.",
                    "refutes_rule": "The frozen treatment excluded a mature, observable cash engine without a responsibility-matched reason.",
                    "mixed_rule": "Implementation improves but unit economics or cash remain non-diagnostic.",
                }
            ],
            "settlement_route": "Use the existing append-only cutoff settlement control plane.",
            "learning_route": "Only accepted feedback may create a judgment-learning note for another case.",
        },
        "transfer_acceptance": {
            "baseline_policy": "Common cutoff evidence and budget only.",
            "enhanced_policy": "Same inputs plus the compiled training memory.",
            "agent_isolation": "Separate fresh agents with no sibling or parent context.",
            "reviewer_blinding": "Review anonymous arms before any outcome access.",
            "decisive_surfaces": [
                "CENTRAL_THESIS",
                "BUSINESS_ENGINE",
                "OWNER_CASH",
                "PERMANENT_LOSS",
                "VALUE_ROUTE",
                "PRICE_IDENTITY",
                "STRONGEST_RIVAL",
                "REVERSAL_EVIDENCE",
                "SOURCE_BINDING",
            ],
            "pass_rule": "Enhanced avoids a material correction or improves a material treatment without a new material error.",
            "failure_rule": "Longer prose, more fields, more caveats or unchanged treatment is not utility.",
            "report_gate": "No open material finding in the existing golden-report review return.",
            "claim_limit": "One positive unseen case creates a transfer candidate only.",
        },
        "authority": "TRAINING_MEMORY_ONLY_NOT_CURRENT_INVESTMENT_EVIDENCE",
    }


def test_valid_teacher_package_is_training_ready(tmp_path: Path) -> None:
    result = validate_teacher_package(_package(tmp_path))
    assert result["state"] == "TRAINING_READY"
    assert result["findings"] == []


def test_transfer_text_rejects_teacher_identity_and_price(tmp_path: Path) -> None:
    package = _package(tmp_path)
    package["correction_events"][0]["transfer"]["portable_rule"] = (
        "教师公司和 00001 证明 2.64 可以迁移。"
    )
    findings = validate_teacher_package(package)["findings"]
    assert any("contains_teacher_company_name" in item for item in findings)
    assert any("contains_teacher_company_id_token" in item for item in findings)
    assert any("contains_currency_or_price" in item for item in findings)


def test_compiled_principle_identity_is_also_portable(tmp_path: Path) -> None:
    package = _package(tmp_path)
    package["conditional_principles"][0]["title"] = "教师公司的原则"
    findings = validate_teacher_package(package)["findings"]
    assert any("contains_teacher_company_name" in item for item in findings)


def test_correction_requires_accepted_review_or_handoff(tmp_path: Path) -> None:
    package = _package(tmp_path)
    package["correction_events"][0]["accepted_source_artifact_ids"] = ["SOURCE:REPORT"]
    findings = validate_teacher_package(package)["findings"]
    assert "correction_events[0].accepted_review_or_handoff_required" in findings


def test_principle_requires_misuse_countercondition_and_target_evidence(tmp_path: Path) -> None:
    package = _package(tmp_path)
    package["conditional_principles"][0]["common_misuse"] = ""
    package["conditional_principles"][0]["counterconditions"] = []
    package["conditional_principles"][0]["target_company_evidence"] = []
    findings = validate_teacher_package(package)["findings"]
    assert "conditional_principles[0].common_misuse_missing" in findings
    assert "conditional_principles[0].counterconditions_missing_or_invalid" in findings
    assert "conditional_principles[0].target_company_evidence_missing_or_invalid" in findings


def test_acceptance_requires_all_material_report_surfaces(tmp_path: Path) -> None:
    package = _package(tmp_path)
    package["transfer_acceptance"]["decisive_surfaces"].remove("OWNER_CASH")
    findings = validate_teacher_package(package)["findings"]
    assert "transfer_acceptance.required_surfaces_missing:OWNER_CASH" in findings


def test_compiler_drops_case_specific_error_and_provenance(tmp_path: Path) -> None:
    package = _package(tmp_path)
    package["correction_events"][0]["before_error_pattern"] = (
        "教师公司 was previously assigned a specific action price."
    )
    memory = compile_training_memory(package)
    assert "教师公司" not in memory
    assert "HK:00001" not in memory
    assert "specific action price" not in memory
    assert str(tmp_path) not in memory
    assert "TRAINING_MEMORY_ONLY_NOT_TARGET_COMPANY_EVIDENCE" in memory
    assert "A complete calculation does not establish" in memory


def test_checked_in_teacher_memory_matches_compiler() -> None:
    campaign = (
        ROOT
        / "docs/development/research/training_campaigns/EXPERT_CORRECTION_CN02669_20260831"
    )
    package = json.loads(
        (campaign / "01_TEACHER_PACKAGE.json").read_text(encoding="utf-8")
    )
    assert validate_teacher_package(package)["state"] == "TRAINING_READY"
    assert (campaign / "02_COMPILED_TRAINING_MEMORY.md").read_text(
        encoding="utf-8"
    ) == compile_training_memory(package)
