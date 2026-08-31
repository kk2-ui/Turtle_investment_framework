from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from scripts.enterprise_underwriting_training import (
    CONTRACT_SCHEMA,
    build_fresh_subagent_task,
    build_training_contract,
)
from scripts.report_autonomy_multicompany_prereg import (
    ARMS,
    _expected_episode_order,
    CUSTODIAN_MAPPING_SCHEMA_VERSION,
    validate_custodian_arm_mapping,
    validate_multicompany_preregistration,
)


def _source(source_id: str, source_ref: str, role: str) -> dict[str, str]:
    return {
        "source_id": source_id,
        "source_ref": source_ref,
        "available_at": "2018-04-30T12:00:00+08:00",
        "time_role": role,
    }


def _feedback_clocks() -> list[dict[str, object]]:
    return [
        {
            "clock_id": "CLOCK:EARLY",
            "horizon": "EARLY_SIGNAL",
            "opens_at": "2019-05-01T00:00:00+08:00",
            "episode_claims": ["INDUSTRY_AND_SITUATION"],
            "discriminating_observation": "Official annual report observation.",
        },
        {
            "clock_id": "CLOCK:CASH",
            "horizon": "NORMALIZATION_AND_CASH",
            "opens_at": "2020-05-01T00:00:00+08:00",
            "episode_claims": ["NORMAL_EARNINGS", "OWNER_CASH"],
            "discriminating_observation": "Official annual report cash observation.",
        },
    ]


def _memory(source_id: str, source_ref: str, kind: str) -> dict[str, object]:
    return {
        **_source(source_id, source_ref, "TRAINING_MEMORY"),
        "memory_kind": kind,
        "company_free": True,
        "target_company_evidence_allowed": False,
        "exposure_register_ref": "docs/exposure-register.json",
    }


def _anonymous_label(index: int) -> str:
    alphabet = "BCDFGHJKLMNPQRSTVWXYZ"
    offset = index % len(alphabet)
    if index < len(alphabet):
        token = alphabet[offset:] + alphabet[:offset]
    else:
        reverse = alphabet[::-1]
        token = reverse[offset:] + reverse[:offset]
    return "ANON_" + token[:12]


def _cell(
    case: dict[str, object], arm_id: str, *, number: int,
) -> dict[str, object]:
    allowed_sources = list(case["common_sources"])
    if arm_id in {"A01", "A11"}:
        allowed_sources.append({
            key: case["industry_memory"][key]
            for key in ("source_id", "source_ref", "available_at", "time_role")
        })
    if arm_id in {"A10", "A11"}:
        allowed_sources.append({
            key: case["expert_memory"][key]
            for key in ("source_id", "source_ref", "available_at", "time_role")
        })
    contract = build_training_contract(
        contract_id=f"UWTRAIN:COHORT:{case['case_id']}:{arm_id}",
        training_track="BLIND_REPLAY",
        company_id=str(case["company_id"]),
        company_name=str(case["company_name"]),
        cutoff_at=str(case["cutoff_at"]),
        allowed_sources=allowed_sources,
        feedback_clocks=_feedback_clocks(),
    )
    return {
        "case_id": case["case_id"],
        "arm_id": arm_id,
        "source_package_ref": case["common_source_package_ref"],
        "training_contract": contract,
        "rendered_task": build_fresh_subagent_task(contract),
        "state": "NOT_STARTED",
        "attempts": {"episode": 0, "reader_report": 0},
        "artifact_paths": {
            "contract_ref": f"contracts/{number:02d}_{arm_id}.json",
            "rendered_task_ref": f"tasks/{number:02d}_{arm_id}.json",
            "raw_response_ref": f"responses/{number:02d}_{arm_id}.json",
            "episode_ref": f"episodes/{number:02d}_{arm_id}.json",
            "reader_bridge_ref": f"bridges/{number:02d}_{arm_id}.json",
            "first_reader_report_ref": f"reports/{number:02d}_{arm_id}.md",
            "freeze_receipt_ref": f"receipts/{number:02d}_{arm_id}.json",
        },
    }


@pytest.fixture(scope="module")
def preregistration(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("report-autonomy-cohort")
    industry_ref = root / "industry-memory.md"
    expert_ref = root / "expert-memory.md"
    industry_ref.write_text("Company-free industry questions.", encoding="utf-8")
    expert_ref.write_text("Company-free correction principles.", encoding="utf-8")
    cases: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    for number in range(1, 9):
        case_id = f"CASE:{number:02d}"
        company_id = f"CN:80{number:04d}"
        source_path = root / f"{case_id}.md"
        source_path.write_text("Cutoff-only common source package.", encoding="utf-8")
        candidate = {
            "candidate_id": f"CANDIDATE:{number:02d}",
            "company_id": company_id,
            "company_name": f"Synthetic Issuer {number}",
            "cutoff_at": "2018-04-30T23:59:59+08:00",
            "stratum_id": "STRATUM:ONE",
            "rank_in_stratum": number,
            "candidate_evidence_ref": str(source_path),
            "common_source_package_ref": str(source_path),
            "source_available_at": "2018-04-30T12:00:00+08:00",
            "eligibility": "ELIGIBLE",
            "exclusion_reason": "NOT_APPLICABLE",
        }
        candidates.append(candidate)
        cases.append({
            "case_id": case_id,
            "candidate_id": candidate["candidate_id"],
            "selection_rank": number,
            "company_id": company_id,
            "company_name": candidate["company_name"],
            "cutoff_at": candidate["cutoff_at"],
            "stratum_id": "STRATUM:ONE",
            "common_source_package_ref": str(source_path),
            "common_sources": [_source(
                f"SRC:{case_id}", str(source_path), "PRE_CUTOFF",
            )],
            "industry_memory": _memory(
                "MEMORY:INDUSTRY", str(industry_ref), "INDUSTRY_DECISION_MEMORY",
            ),
            "expert_memory": _memory(
                "MEMORY:EXPERT", str(expert_ref), "EXPERT_CORRECTION_MEMORY",
            ),
        })

    cells = [
        _cell(case, arm_id, number=number)
        for number, case in enumerate(cases, start=1)
        for arm_id in ARMS
    ]
    mapping = [
        {
            "case_id": cell["case_id"],
            "arm_id": cell["arm_id"],
            "anonymous_label": _anonymous_label(index),
            "source_package_ref": cell["source_package_ref"],
        }
        for index, cell in enumerate(cells, start=1)
    ]
    manifest = [
        {
            "case_id": mapping[index]["case_id"],
            "anonymous_label": mapping[index]["anonymous_label"],
            "source_package_ref": cell["source_package_ref"],
            "episode_ref": f"anonymous/episode_{index:02d}.json",
            "reader_bridge_ref": f"anonymous/bridge_{index:02d}.json",
            "first_reader_report_ref": f"anonymous/report_{index:02d}.md",
        }
        for index, cell in enumerate(cells)
    ]
    return {
        "schema_version": "report-autonomy-multicompany-preregistration.v1",
        "preregistration_id": "REPORT_AUTONOMY_2X2_MULTICOMPANY:TEST",
        "state": "COHORT_FROZEN",
        "cohort": {
            "selection_policy": "CUTOFF_ONLY_FIXED_STRATUM_RANK",
            "replacement_policy": "NO_REPLACEMENTS_AFTER_COHORT_FREEZE",
            "replacement_records": [],
            "strata": [{"stratum_id": "STRATUM:ONE", "quota": 8}],
            "candidate_universe": candidates,
        },
        "cases": cases,
        "execution": {
            "schema_version": CONTRACT_SCHEMA,
            "retry_policy": "NO_RETRY_OR_REWRITE",
            "cell_budget": {
                "episode_attempts": 1,
                "reader_report_attempts": 1,
                "max_episode_words": 3000,
                "max_reader_report_words": 5000,
                "episode_time_limit_seconds": 1800,
                "reader_report_time_limit_seconds": 1800,
            },
            "tool_policy": {
                "network_access": "PROHIBITED",
                "repository_browsing": "PROHIBITED",
                "parent_context_access": "PROHIBITED",
                "sibling_output_access": "PROHIBITED",
                "outcome_price_return_access": "PROHIBITED",
            },
            "schedule": {
                "episode_orders": {
                    case["case_id"]: _expected_episode_order(case["selection_rank"])
                    for case in cases
                },
                "reader_report_orders": {
                    case["case_id"]: (
                        _expected_episode_order(case["selection_rank"])[2:]
                        + _expected_episode_order(case["selection_rank"])[:2]
                    ) for case in cases
                },
            },
            "cells": cells,
        },
        "anonymous_review_custody": {
            "reviewer_manifest": manifest,
        },
        "outcome_measurements": [{
            "case_id": case["case_id"],
            "company_id": case["company_id"],
            "cutoff_at": case["cutoff_at"],
            "measurement_contract_ref": f"measurements/{case['case_id']}.json",
            "outcome_window": "FY2018_TO_FY2022",
            "official_source_category": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "first_complete_annual_report_rule": "FIRST_COMPLETE_FISCAL_YEAR_AFTER_CUTOFF",
            "field_boundary_rule": "LISTED_ISSUER_CONSOLIDATED",
            "mismatch_rule": "PRESERVE_SOURCE_MISMATCH",
            "disposition_rule": "SUPPORTED_WEAKENED_OR_FALSIFIED_INCONCLUSIVE_DATA_NON_DISCRIMINATING",
        } for case in cases],
        "outcome_access_gate": {
            "state": "BLOCKED_UNTIL_ALL_ANONYMOUS_PREOUTCOME_REVIEWS_FROZEN",
            "outcome_access_authorized": False,
            "required_reviewer_freeze_receipts": sorted(case["case_id"] for case in cases),
        },
    }


@pytest.fixture(scope="module")
def custodian_mapping(preregistration: dict[str, object]) -> dict[str, object]:
    mappings: list[dict[str, object]] = []
    for case in preregistration["cases"]:
        case_id = case["case_id"]
        case_cells = [
            cell for cell in preregistration["execution"]["cells"]
            if cell["case_id"] == case_id
        ]
        case_manifest = [
            item for item in preregistration["anonymous_review_custody"]["reviewer_manifest"]
            if item["case_id"] == case_id
        ]
        for cell, item in zip(case_cells, case_manifest, strict=True):
            mappings.append({
                "case_id": case_id,
                "arm_id": cell["arm_id"],
                "anonymous_label": item["anonymous_label"],
                "source_package_ref": item["source_package_ref"],
                "source_episode_ref": cell["artifact_paths"]["episode_ref"],
                "source_reader_bridge_ref": cell["artifact_paths"]["reader_bridge_ref"],
                "source_first_reader_report_ref": cell["artifact_paths"]["first_reader_report_ref"],
            })
    return {
        "schema_version": CUSTODIAN_MAPPING_SCHEMA_VERSION,
        "preregistration_id": preregistration["preregistration_id"],
        "visibility": "CUSTODIAN_ONLY",
        "mappings": mappings,
    }


def _validate(bundle: dict[str, object]) -> list[str]:
    result = validate_multicompany_preregistration(bundle)
    return result["findings"]


def test_preregistration_accepts_a_balanced_8x4_preoutcome_cohort(
    preregistration: dict[str, object],
) -> None:
    result = validate_multicompany_preregistration(preregistration)
    assert result["state"] == "REVIEWABLE"
    assert result["case_count"] == 8
    assert result["expected_cell_count"] == 32


def test_custodian_mapping_completes_the_hidden_case_arm_bijection(
    preregistration: dict[str, object], custodian_mapping: dict[str, object],
) -> None:
    assert validate_custodian_arm_mapping(preregistration, custodian_mapping)["state"] == "REVIEWABLE"


def test_preregistration_rejects_duplicate_company_and_postfreeze_replacement(
    preregistration: dict[str, object],
) -> None:
    bundle = deepcopy(preregistration)
    bundle["cases"][1]["company_id"] = bundle["cases"][0]["company_id"]
    bundle["cohort"]["replacement_records"] = ["CANDIDATE:09"]
    findings = _validate(bundle)
    assert "cases[1].company_id_missing_or_duplicate" in findings
    assert "cohort.replacement_records_must_be_empty" in findings


def test_preregistration_rejects_cross_arm_common_source_drift(
    preregistration: dict[str, object], tmp_path: Path,
) -> None:
    bundle = deepcopy(preregistration)
    other_source = tmp_path / "other-common-source.md"
    other_source.write_text("Other cutoff source.", encoding="utf-8")
    cell = next(item for item in bundle["execution"]["cells"] if item["arm_id"] == "A01")
    cell["training_contract"]["allowed_sources"][0]["source_ref"] = str(other_source)
    cell["rendered_task"] = build_fresh_subagent_task(cell["training_contract"])
    findings = _validate(bundle)
    assert any("common_sources_mismatch" in finding for finding in findings)
    assert any("case_common_contract_mismatch" in finding for finding in findings)


def test_preregistration_rejects_non_training_memory_and_attempt_retry(
    preregistration: dict[str, object],
) -> None:
    bundle = deepcopy(preregistration)
    bundle["cases"][0]["industry_memory"]["time_role"] = "PRE_CUTOFF"
    bundle["execution"]["cells"][0]["attempts"]["episode"] = 2
    findings = _validate(bundle)
    assert "cases[0].industry_memory.time_role_must_be_training_memory" in findings
    assert "execution.cells[0].attempts.episode_must_be_zero_or_one" in findings


def test_preregistration_rejects_anonymity_leak_and_early_outcome_access(
    preregistration: dict[str, object],
) -> None:
    bundle = deepcopy(preregistration)
    bundle["anonymous_review_custody"]["mapping"] = []
    bundle["anonymous_review_custody"]["reviewer_manifest"][1]["anonymous_label"] = "ANON_01"
    bundle["anonymous_review_custody"]["reviewer_manifest"][0]["episode_ref"] = "episodes/A00.json"
    bundle["outcome_access_gate"]["outcome_access_authorized"] = True
    findings = _validate(bundle)
    assert "anonymous_review_custody.unexpected_fields:mapping" in findings
    assert "anonymous_review_custody.reviewer_manifest[1].anonymous_label_must_be_opaque" in findings
    assert "anonymous_review_custody.reviewer_manifest_contains_arm_identifier" in findings
    assert "outcome_access_gate.must_be_unauthorized_preoutcome" in findings


def test_preregistration_rejects_measurement_identity_drift(
    preregistration: dict[str, object],
) -> None:
    bundle = deepcopy(preregistration)
    bundle["outcome_measurements"][0]["cutoff_at"] = "2018-05-01T00:00:00+08:00"
    assert "outcome_measurements[0].cutoff_at_mismatch" in _validate(bundle)
