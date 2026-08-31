#!/usr/bin/env python3
"""Generate the deterministic, frozen Appliance Stage-5 2x2 register.

The generator is intentionally a control-plane builder.  It never reads an
outcome, executes an arm, writes an arm artifact, or changes cohort state.  Its
only product is an inline register containing current v2 training contracts and
their exact freshly rendered tasks.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any

try:
    from scripts.enterprise_underwriting_training import (
        CONTRACT_SCHEMA,
        ECONOMIC_DERIVATION_INTERFACE,
        build_fresh_subagent_task,
        build_training_contract,
    )
    from scripts.report_autonomy_multicompany_prereg import (
        ARMS,
        _expected_episode_order,
        validate_multicompany_preregistration,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.enterprise_underwriting_training import (
        CONTRACT_SCHEMA,
        ECONOMIC_DERIVATION_INTERFACE,
        build_fresh_subagent_task,
        build_training_contract,
    )
    from scripts.report_autonomy_multicompany_prereg import (
        ARMS,
        _expected_episode_order,
        validate_multicompany_preregistration,
    )


INPUT_SCHEMA = "report-autonomy-appliance-cohort-prereg-input.v1"
PREREGISTRATION_SCHEMA = "report-autonomy-multicompany-preregistration.v1"
PREREGISTRATION_STATE = "COHORT_FROZEN"

INDUSTRY_MEMORY_REF = (
    "docs/development/research/industry_learning_blocks/"
    "CN_APPLIANCE_2017_2018/09_compact_industry_decision_memory_v1.md"
)
EXPERT_CORRECTION_MEMORY_REF = (
    "docs/development/research/training_campaigns/"
    "EXPERT_CORRECTION_CN02669_20260831/02_COMPILED_TRAINING_MEMORY.md"
)
INDUSTRY_MEMORY_AVAILABLE_AT = "2026-09-01T00:00:00+08:00"
EXPERT_CORRECTION_MEMORY_AVAILABLE_AT = "2026-08-31T00:00:00+08:00"

EXPECTED_COMPANY_IDS = (
    "CN:000016",
    "CN:000404",
    "CN:002403",
    "CN:002543",
    "CN:002614",
    "CN:002676",
    "CN:002705",
    "CN:603355",
)

_INPUT_FIELDS = {
    "schema_version",
    "preregistration_id",
    "cutoff_at",
    "stratum_id",
    "candidate_universe",
    "reviewer_labels_by_selection_rank",
    "industry_memory_ref",
    "expert_correction_memory_ref",
    "exposure_ledger_ref",
}
_INPUT_LABEL_GROUP_FIELDS = {"selection_rank", "anonymous_labels"}
_INPUT_CANDIDATE_FIELDS = {
    "candidate_id",
    "company_id",
    "company_name",
    "rank_in_stratum",
    "candidate_evidence_ref",
    "common_source_package_ref",
    "source_available_at",
    "eligibility",
    "exclusion_reason",
}
_ARTIFACT_ROOT = (
    "docs/development/research/training_campaigns/"
    "REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_20181231/execution"
)
_TOOL_POLICY = {
    "network_access": "PROHIBITED",
    "repository_browsing": "PROHIBITED",
    "parent_context_access": "PROHIBITED",
    "sibling_output_access": "PROHIBITED",
    "outcome_price_return_access": "PROHIBITED",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _parse_instant(value: Any) -> datetime | None:
    text = _text(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _next_year(value: str, years: int) -> str:
    """Derive a feedback opening instant without consulting any outcome data."""

    parsed = _parse_instant(value)
    if parsed is None:  # Input validation supplies the user-facing error.
        raise ValueError("cutoff_at_invalid")
    return parsed.replace(year=parsed.year + years).isoformat()


def validate_appliance_cohort_input(config: Any) -> list[str]:
    """Validate the small declared input surface before generating anything."""

    findings: list[str] = []
    value = _mapping(config)
    if not value:
        return ["input.must_be_object"]
    extra = sorted(set(value) - _INPUT_FIELDS)
    missing = sorted(_INPUT_FIELDS - set(value))
    if extra:
        findings.append("input.unexpected_fields:" + ",".join(extra))
    if missing:
        findings.append("input.missing_fields:" + ",".join(missing))
    if value.get("schema_version") != INPUT_SCHEMA:
        findings.append("input.schema_version_invalid")
    for field in ("preregistration_id", "stratum_id", "exposure_ledger_ref"):
        if not _text(value.get(field)):
            findings.append("input." + field + "_required")
    if _parse_instant(value.get("cutoff_at")) is None:
        findings.append("input.cutoff_at_invalid")
    if value.get("industry_memory_ref") != INDUSTRY_MEMORY_REF:
        findings.append("input.industry_memory_ref_must_be_declared_appliance_memory")
    if value.get("expert_correction_memory_ref") != EXPERT_CORRECTION_MEMORY_REF:
        findings.append("input.expert_correction_memory_ref_must_be_declared_correction_memory")

    candidates = [_mapping(item) for item in _items(value.get("candidate_universe"))]
    if len(candidates) < len(EXPECTED_COMPANY_IDS):
        findings.append("input.candidate_universe_must_include_the_eight_selected_candidates")
        return findings

    company_ids: set[str] = set()
    candidate_ids: set[str] = set()
    source_refs: set[str] = set()
    ranks: list[int] = []
    eligible_company_ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        path = f"input.candidate_universe[{index}]"
        extra = sorted(set(candidate) - _INPUT_CANDIDATE_FIELDS)
        missing = sorted(_INPUT_CANDIDATE_FIELDS - set(candidate))
        if extra:
            findings.append(path + ".unexpected_fields:" + ",".join(extra))
        if missing:
            findings.append(path + ".missing_fields:" + ",".join(missing))
        for field in ("candidate_id", "company_id", "company_name", "candidate_evidence_ref"):
            item = _text(candidate.get(field))
            if not item:
                findings.append(path + "." + field + "_required")
                continue
            if field == "candidate_id":
                if item in candidate_ids:
                    findings.append(path + ".candidate_id_duplicate")
                candidate_ids.add(item)
            elif field == "company_id":
                if item in company_ids:
                    findings.append(path + ".company_id_duplicate")
                company_ids.add(item)
        rank = candidate.get("rank_in_stratum")
        if not isinstance(rank, int) or isinstance(rank, bool):
            findings.append(path + ".rank_in_stratum_invalid")
        else:
            ranks.append(rank)
        eligibility = candidate.get("eligibility")
        source_ref = _text(candidate.get("common_source_package_ref"))
        source_available_at = _text(candidate.get("source_available_at"))
        if eligibility == "ELIGIBLE":
            eligible_company_ids.add(_text(candidate.get("company_id")))
            if not source_ref or source_ref == "NOT_APPLICABLE":
                findings.append(path + ".eligible_common_source_package_ref_required")
            elif source_ref in source_refs:
                findings.append(path + ".common_source_package_ref_duplicate")
            else:
                source_refs.add(source_ref)
            available = _parse_instant(source_available_at)
            cutoff = _parse_instant(value.get("cutoff_at"))
            if available is None or (cutoff is not None and available > cutoff):
                findings.append(path + ".eligible_source_available_at_invalid_or_after_cutoff")
            if candidate.get("exclusion_reason") != "NOT_APPLICABLE":
                findings.append(path + ".eligible_exclusion_reason_must_be_not_applicable")
        elif eligibility == "EXCLUDED":
            if not _text(candidate.get("exclusion_reason")) or candidate.get("exclusion_reason") == "NOT_APPLICABLE":
                findings.append(path + ".excluded_reason_required")
            if source_ref not in {"", "NOT_APPLICABLE"}:
                findings.append(path + ".excluded_common_source_package_ref_must_be_not_applicable")
            if source_available_at not in {"", "NOT_APPLICABLE"}:
                findings.append(path + ".excluded_source_available_at_must_be_not_applicable")
        else:
            findings.append(path + ".eligibility_invalid")

    if eligible_company_ids != set(EXPECTED_COMPANY_IDS):
        findings.append("input.eligible_candidates_must_match_declared_eight_company_ids")
    if sorted(ranks) != list(range(1, len(candidates) + 1)):
        findings.append("input.ranks_must_be_one_through_candidate_universe")

    label_groups = [_mapping(item) for item in _items(
        value.get("reviewer_labels_by_selection_rank")
    )]
    if len(label_groups) != len(EXPECTED_COMPANY_IDS):
        findings.append("input.reviewer_label_groups_must_cover_eight_selected_cases")
    group_ranks: set[int] = set()
    labels: set[str] = set()
    for index, group in enumerate(label_groups):
        path = f"input.reviewer_labels_by_selection_rank[{index}]"
        extra = sorted(set(group) - _INPUT_LABEL_GROUP_FIELDS)
        missing = sorted(_INPUT_LABEL_GROUP_FIELDS - set(group))
        if extra:
            findings.append(path + ".unexpected_fields:" + ",".join(extra))
        if missing:
            findings.append(path + ".missing_fields:" + ",".join(missing))
        rank = group.get("selection_rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank in group_ranks:
            findings.append(path + ".selection_rank_missing_invalid_or_duplicate")
        else:
            group_ranks.add(rank)
        group_labels = _items(group.get("anonymous_labels"))
        if len(group_labels) != len(ARMS):
            findings.append(path + ".must_contain_exactly_four_anonymous_labels")
        for label_index, raw_label in enumerate(group_labels):
            label = _text(raw_label)
            if not re.fullmatch(
                r"ANON_[BCDFGHJKLMNPQRSTVWXYZ]{12}", label,
            ) or label in labels:
                findings.append(
                    path + f".anonymous_labels[{label_index}]_missing_invalid_or_duplicate"
                )
            else:
                labels.add(label)
    if group_ranks != set(range(1, len(EXPECTED_COMPANY_IDS) + 1)):
        findings.append("input.reviewer_label_groups_must_have_selection_ranks_one_through_eight")
    return list(dict.fromkeys(findings))


def _memory(
    *, source_id: str, source_ref: str, available_at: str, memory_kind: str,
    exposure_ledger_ref: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_ref": source_ref,
        "available_at": available_at,
        "time_role": "TRAINING_MEMORY",
        "memory_kind": memory_kind,
        "company_free": True,
        "target_company_evidence_allowed": False,
        "exposure_register_ref": exposure_ledger_ref,
    }


def _feedback_clocks(cutoff_at: str) -> list[dict[str, Any]]:
    return [
        {
            "clock_id": "CLOCK:EARLY_SIGNAL",
            "horizon": "EARLY_SIGNAL",
            "opens_at": _next_year(cutoff_at, 1),
            "episode_claims": ["INDUSTRY_AND_SITUATION"],
            "discriminating_observation": (
                "Post-cutoff official annual-report observation after the gate opens."
            ),
        },
        {
            "clock_id": "CLOCK:NORMALIZATION_AND_CASH",
            "horizon": "NORMALIZATION_AND_CASH",
            "opens_at": _next_year(cutoff_at, 2),
            "episode_claims": ["NORMAL_EARNINGS", "OWNER_CASH"],
            "discriminating_observation": (
                "Later post-cutoff official annual-report observation after the gate opens."
            ),
        },
    ]


def _artifact_paths(case_number: int, arm_id: str) -> dict[str, str]:
    root = f"{_ARTIFACT_ROOT}/case_{case_number:02d}/{arm_id}"
    return {
        "contract_ref": root + "/training_contract.json",
        "rendered_task_ref": root + "/fresh_task.json",
        "raw_response_ref": root + "/raw_response.json",
        "episode_ref": root + "/enterprise_underwriting_episode.json",
        "reader_bridge_ref": root + "/reader_bridge.json",
        "first_reader_report_ref": root + "/first_reader_report.md",
        "freeze_receipt_ref": root + "/freeze_receipt.json",
    }


def _anonymous_manifest_entry(
    case_id: str, anonymous_label: str, source_package_ref: str,
) -> dict[str, str]:
    root = f"{_ARTIFACT_ROOT}/anonymous/{anonymous_label.lower()}"
    return {
        "case_id": case_id,
        "anonymous_label": anonymous_label,
        "source_package_ref": source_package_ref,
        "episode_ref": root + "/episode.json",
        "reader_bridge_ref": root + "/reader_bridge.json",
        "first_reader_report_ref": root + "/first_reader_report.md",
    }


def build_appliance_cohort_preregistration(config: Any) -> dict[str, Any]:
    """Build all 32 unexecuted cells from the declared Appliance input only."""

    findings = validate_appliance_cohort_input(config)
    if findings:
        raise ValueError("appliance_cohort_input_invalid:" + ",".join(findings))
    value = _mapping(config)
    cutoff_at = _text(value["cutoff_at"])
    stratum_id = _text(value["stratum_id"])
    candidates = sorted(
        (deepcopy(_mapping(candidate)) for candidate in _items(value["candidate_universe"])),
        key=lambda candidate: int(candidate["rank_in_stratum"]),
    )
    selected_candidates = [
        candidate for candidate in candidates if candidate["eligibility"] == "ELIGIBLE"
    ]
    reviewer_labels_by_selection_rank = {
        int(group["selection_rank"]): [
            _text(label) for label in _items(group["anonymous_labels"])
        ]
        for group in (
            _mapping(item)
            for item in _items(value["reviewer_labels_by_selection_rank"])
        )
    }
    industry_memory = _memory(
        source_id="MEMORY:INDUSTRY_DECISION:CN_APPLIANCE_2017_2018",
        source_ref=INDUSTRY_MEMORY_REF,
        available_at=INDUSTRY_MEMORY_AVAILABLE_AT,
        memory_kind="INDUSTRY_DECISION_MEMORY",
        exposure_ledger_ref=_text(value["exposure_ledger_ref"]),
    )
    expert_memory = _memory(
        source_id="MEMORY:EXPERT_CORRECTION:CN02669:20260831",
        source_ref=EXPERT_CORRECTION_MEMORY_REF,
        available_at=EXPERT_CORRECTION_MEMORY_AVAILABLE_AT,
        memory_kind="EXPERT_CORRECTION_MEMORY",
        exposure_ledger_ref=_text(value["exposure_ledger_ref"]),
    )
    cases: list[dict[str, Any]] = []
    output_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        output_candidates.append({
            "candidate_id": _text(candidate["candidate_id"]),
            "company_id": _text(candidate["company_id"]),
            "company_name": _text(candidate["company_name"]),
            "cutoff_at": cutoff_at,
            "stratum_id": stratum_id,
            "rank_in_stratum": candidate["rank_in_stratum"],
            "candidate_evidence_ref": _text(candidate["candidate_evidence_ref"]),
            "common_source_package_ref": _text(candidate["common_source_package_ref"]),
            "source_available_at": _text(candidate["source_available_at"]),
            "eligibility": candidate["eligibility"],
            "exclusion_reason": candidate["exclusion_reason"],
        })
    for rank, candidate in enumerate(selected_candidates, start=1):
        company_id = _text(candidate["company_id"])
        common_source = {
            "source_id": "SRC:PRE_CUTOFF_PACKAGE:" + company_id.replace(":", ""),
            "source_ref": _text(candidate["common_source_package_ref"]),
            "available_at": _text(candidate["source_available_at"]),
            "time_role": "PRE_CUTOFF",
        }
        output_candidate = next(
            item for item in output_candidates
            if item["candidate_id"] == _text(candidate["candidate_id"])
        )
        case = {
            "case_id": f"CASE:{rank:02d}",
            "candidate_id": output_candidate["candidate_id"],
            "selection_rank": rank,
            "company_id": company_id,
            "company_name": output_candidate["company_name"],
            "cutoff_at": cutoff_at,
            "stratum_id": stratum_id,
            "common_source_package_ref": common_source["source_ref"],
            "common_sources": [common_source],
            "industry_memory": deepcopy(industry_memory),
            "expert_memory": deepcopy(expert_memory),
        }
        cases.append(case)

    cells: list[dict[str, Any]] = []
    for case_number, case in enumerate(cases, start=1):
        for arm_id in ARMS:
            allowed_sources = deepcopy(case["common_sources"])
            if arm_id in {"A01", "A11"}:
                allowed_sources.append({
                    field: case["industry_memory"][field]
                    for field in ("source_id", "source_ref", "available_at", "time_role")
                })
            if arm_id in {"A10", "A11"}:
                allowed_sources.append({
                    field: case["expert_memory"][field]
                    for field in ("source_id", "source_ref", "available_at", "time_role")
                })
            contract = build_training_contract(
                contract_id=(
                    "UWTRAIN:APPLIANCE:" + case["company_id"].replace("CN:", "")
                    + ":" + cutoff_at[:10].replace("-", "")
                    + ":STAGE5:" + arm_id + ":V2"
                ),
                training_track="BLIND_REPLAY",
                company_id=case["company_id"],
                company_name=case["company_name"],
                cutoff_at=cutoff_at,
                allowed_sources=allowed_sources,
                feedback_clocks=_feedback_clocks(cutoff_at),
                economic_derivation_interface=ECONOMIC_DERIVATION_INTERFACE,
            )
            cells.append({
                "case_id": case["case_id"],
                "arm_id": arm_id,
                "source_package_ref": case["common_source_package_ref"],
                "training_contract": contract,
                "rendered_task": build_fresh_subagent_task(contract),
                "state": "NOT_STARTED",
                "attempts": {"episode": 0, "reader_report": 0},
                "artifact_paths": _artifact_paths(case_number, arm_id),
            })
    manifest = sorted(
        (
            _anonymous_manifest_entry(
                case["case_id"],
                anonymous_label,
                case["common_source_package_ref"],
            )
            for case in cases
            for anonymous_label in reviewer_labels_by_selection_rank[
                case["selection_rank"]
            ]
        ),
        key=lambda item: item["anonymous_label"],
    )

    preregistration = {
        "schema_version": PREREGISTRATION_SCHEMA,
        "preregistration_id": _text(value["preregistration_id"]),
        "state": PREREGISTRATION_STATE,
        "cohort": {
            "selection_policy": "CUTOFF_ONLY_FIXED_STRATUM_RANK",
            "replacement_policy": "NO_REPLACEMENTS_AFTER_COHORT_FREEZE",
            "replacement_records": [],
            "strata": [{"stratum_id": stratum_id, "quota": len(selected_candidates)}],
            "candidate_universe": output_candidates,
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
            "tool_policy": deepcopy(_TOOL_POLICY),
            "schedule": {
                "episode_orders": {
                    case["case_id"]: _expected_episode_order(case["selection_rank"])
                    for case in cases
                },
                "reader_report_orders": {
                    case["case_id"]: (
                        _expected_episode_order(case["selection_rank"])[2:]
                        + _expected_episode_order(case["selection_rank"])[:2]
                    )
                    for case in cases
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
            "cutoff_at": cutoff_at,
            "measurement_contract_ref": (
                f"{_ARTIFACT_ROOT}/measurements/{case['case_id'].replace(':', '_')}.json"
            ),
            "outcome_window": "POST_CUTOFF_OFFICIAL_ANNUAL_REPORTS_ONLY",
            "official_source_category": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "first_complete_annual_report_rule": "FIRST_COMPLETE_FISCAL_YEAR_AFTER_CUTOFF",
            "field_boundary_rule": "LISTED_ISSUER_CONSOLIDATED",
            "mismatch_rule": "PRESERVE_SOURCE_MISMATCH",
            "disposition_rule": (
                "SUPPORTED_WEAKENED_OR_FALSIFIED_INCONCLUSIVE_DATA_NON_DISCRIMINATING"
            ),
        } for case in cases],
        "outcome_access_gate": {
            "state": "BLOCKED_UNTIL_ALL_ANONYMOUS_PREOUTCOME_REVIEWS_FROZEN",
            "outcome_access_authorized": False,
            "required_reviewer_freeze_receipts": sorted(
                case["case_id"] for case in cases
            ),
        },
    }
    validation = validate_multicompany_preregistration(preregistration)
    if validation["state"] != "REVIEWABLE":
        raise ValueError(
            "appliance_cohort_preregistration_invalid:"
            + ",".join(validation["findings"])
        )
    return preregistration


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("input_json_must_be_object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_config", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args(argv)
    try:
        preregistration = build_appliance_cohort_preregistration(
            _read_json(args.input_config)
        )
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(
            json.dumps(preregistration, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"state": "INVALID", "findings": [str(exc)]}, ensure_ascii=False))
        return 2
    print(json.dumps(
        validate_multicompany_preregistration(preregistration),
        ensure_ascii=False,
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
