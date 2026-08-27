#!/usr/bin/env python3
"""Project training receipts into an investor-readable learning status.

This module is deliberately read-only.  It does not settle outcomes, approve
learning, alter a method, or grant downstream investment rights.  It answers a
smaller question: what kind of evidence does each completed training round
actually provide under the existing K0/L0-L5 validation ladder?
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA_VERSION = "investor-judgment-learning-input-manifest.v1"
READ_MODEL_SCHEMA_VERSION = "investor-judgment-learning-read-model.v1"
SETTLEMENT_SCHEMA_VERSION = "enterprise-outcome-measurement-settlement.v1"

PROJECTION_TYPES = {
    "ROUND5_LOCAL_JUDGMENT_CHANGE",
    "ROUND6_CROSS_COMPANY_DEVELOPMENT_UTILITY",
    "ROUND7_MULTIDIMENSIONAL_DEVELOPMENT_UTILITY",
    "ROUND8_CROSS_INDUSTRY_NO_ADVANTAGE",
    "ROUND9_METHOD_COMPARISON_INVALID",
}

DOWNSTREAM_RIGHTS = (
    "directional_learning",
    "enterprise_learning",
    "comparative",
    "method_transfer",
    "cjo",
    "valuation",
    "report",
    "investment",
)

LEVEL_DEFINITIONS = {
    "K0": "Industry and teaching assets are traceable.",
    "L0": "PIT, freeze, refusal and boundary controls operate for the recorded episodes.",
    "L1": "Frozen outcome fields are acquired and mechanically settled from official sources.",
    "L2": "A frozen mechanism pair receives an accepted diagnostic verdict under its original predicate.",
    "L3": "A pre-outcome admitted primary path is compared with its strongest rival and fair baseline.",
    "L4": "A settled lesson changes a different company before freeze and is settled under the same definition.",
    "L5": "Multiple independent L3 episodes are compared with a frozen simple baseline and complete denominator.",
}


class LearningReadModelError(ValueError):
    """Raised when a source receipt cannot support the requested projection."""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise LearningReadModelError(field + "_missing")
    return text


def _load_json(repo_root: Path, artifact_ref: str, *, required: bool = True) -> dict[str, Any] | None:
    ref = str(artifact_ref or "").strip()
    if not ref:
        if required:
            raise LearningReadModelError("artifact_ref_missing")
        return None
    path = repo_root / ref
    if not path.is_file():
        raise LearningReadModelError("artifact_missing:" + ref)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LearningReadModelError("artifact_invalid_json:" + ref) from exc
    if not isinstance(value, dict):
        raise LearningReadModelError("artifact_not_object:" + ref)
    return value


def _require_equal(actual: Any, expected: Any, field: str) -> None:
    if actual != expected:
        raise LearningReadModelError(field + "_mismatch")


def _settlement_ref(completion: dict[str, Any]) -> str:
    value = completion.get("settlement_ref")
    if isinstance(value, dict):
        return str(value.get("settlement_id") or "")
    return str(value or "")


def _assert_closed_rights(
    artifact: dict[str, Any],
    artifact_name: str,
    *,
    require_all: bool = False,
) -> None:
    rights = _mapping(artifact.get("rights"))
    if require_all:
        missing = [right for right in DOWNSTREAM_RIGHTS if right not in rights]
        if missing:
            raise LearningReadModelError(f"{artifact_name}_rights_missing:" + ",".join(missing))
    for right in DOWNSTREAM_RIGHTS:
        if right in rights and rights[right] != "NOT_AUTHORIZED":
            raise LearningReadModelError(f"{artifact_name}_right_open:{right}")


def _status_counts(settlement: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    cells = _items(settlement.get("cell_results"))
    if not cells:
        raise LearningReadModelError("settlement_cell_results_missing")
    seen_ids: set[str] = set()
    for cell in cells:
        row = _mapping(cell)
        cell_id = _required_text(row.get("cell_id"), "cell_id")
        if cell_id in seen_ids:
            raise LearningReadModelError("duplicate_cell_id:" + cell_id)
        seen_ids.add(cell_id)
        status = _required_text(row.get("status"), "cell_status")
        counts[status] += 1
    return dict(sorted(counts.items()))


def _normalize_diagnostic_status(value: Any) -> str | None:
    status = str(value or "").strip().upper()
    if not status:
        return None
    for prefix in ("MEASUREMENT_MISMATCH", "NOT_DIAGNOSTIC", "NO_DIFFERENCE", "UNKNOWN", "MIXED"):
        if status.startswith(prefix):
            return prefix
    if status.startswith(("REJECTED", "INVALID", "METHOD_COMPARISON_INVALID")):
        return "INVALIDATED"
    if status.startswith("PARTIAL"):
        return "PARTIAL"
    if status in {"ENHANCED_BETTER", "MATERIAL_IMPROVEMENT"}:
        return "POSITIVE_DEVELOPMENT_UTILITY"
    return "OTHER"


def _diagnostic_statuses(projection_type: str, review: dict[str, Any] | None) -> list[str]:
    if review is None:
        return []
    raw: list[Any] = []
    if projection_type == "ROUND5_LOCAL_JUDGMENT_CHANGE":
        raw.extend(_mapping(item).get("verdict") for item in _mapping(review.get("layer_findings")).values())
    elif projection_type == "ROUND6_CROSS_COMPANY_DEVELOPMENT_UTILITY":
        for item in _items(_mapping(review.get("utility_evaluation")).get("dimension_findings")):
            row = _mapping(item)
            raw.extend((row.get("baseline_assessment"), row.get("enhanced_assessment")))
    elif projection_type == "ROUND7_MULTIDIMENSIONAL_DEVELOPMENT_UTILITY":
        raw.extend(_mapping(item).get("utility_verdict") for item in _items(review.get("dimension_findings")))
    elif projection_type == "ROUND8_CROSS_INDUSTRY_NO_ADVANTAGE":
        for item in _mapping(review.get("accepted_dimension_conclusions")).values():
            row = _mapping(item)
            raw.extend((row.get("baseline_assessment"), row.get("enhanced_assessment")))
    elif projection_type == "ROUND9_METHOD_COMPARISON_INVALID":
        raw.append(review.get("method_feedback_status"))
    return [status for value in raw if (status := _normalize_diagnostic_status(value)) is not None]


def _list_text(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        actions = value.get("actions")
        return _list_text(actions)
    text = str(value or "").strip()
    return [text] if text else []


def _base_projection(
    entry: dict[str, Any],
    completion: dict[str, Any],
    settlement: dict[str, Any],
    review: dict[str, Any] | None,
) -> dict[str, Any]:
    round_id = _required_text(entry.get("round_id"), "round_id")
    projection_type = _required_text(entry.get("projection_type"), "projection_type")
    if projection_type not in PROJECTION_TYPES:
        raise LearningReadModelError("projection_type_invalid:" + projection_type)
    _require_equal(settlement.get("schema_version"), SETTLEMENT_SCHEMA_VERSION, "settlement_schema_version")
    _require_equal(settlement.get("settled"), True, "settlement_state")
    _require_equal(_settlement_ref(completion), settlement.get("settlement_id"), "settlement_ref")
    _require_equal(completion.get("company_id"), settlement.get("company_id"), "company_id")
    _require_equal(completion.get("cutoff_at"), settlement.get("cutoff_at"), "cutoff_at")
    _assert_closed_rights(completion, round_id + "_completion", require_all=True)
    _assert_closed_rights(settlement, round_id + "_settlement")
    if review is not None:
        _assert_closed_rights(review, round_id + "_review")

    measurement_counts = _status_counts(settlement)
    diagnostics = Counter(_diagnostic_statuses(projection_type, review))
    return {
        "round_id": round_id,
        "projection_type": projection_type,
        "evidence_id": _required_text(
            completion.get("completion_id"),
            "completion_id",
        ),
        "company_id": _required_text(completion.get("company_id"), "company_id"),
        "cutoff_at": _required_text(completion.get("cutoff_at"), "cutoff_at"),
        "source_artifacts": {
            "completion": _required_text(entry.get("completion_artifact"), "completion_artifact"),
            "settlement": _required_text(entry.get("settlement_artifact"), "settlement_artifact"),
            "independent_review": str(entry.get("independent_review_artifact") or "").strip() or None,
            "invalidation": str(entry.get("invalidation_artifact") or "").strip() or None,
        },
        "independent_review_present": review is not None,
        "pipeline_proof": {
            "status": "ACCEPTED",
            "strict_level": "L1",
            "statement": (
                f"{sum(measurement_counts.values())} frozen outcome cells were mechanically settled; "
                "unresolved and mismatched cells remain explicit."
            ),
        },
        "measurement_denominator": {
            "total_cells": sum(measurement_counts.values()),
            "status_counts": measurement_counts,
        },
        "diagnostic_denominator": {
            "total_findings": sum(diagnostics.values()),
            "status_counts": dict(sorted(diagnostics.items())),
        },
        "strict_level_ceiling": "L1",
        "rights": {right: "NOT_AUTHORIZED" for right in DOWNSTREAM_RIGHTS},
    }


def _project_entry(repo_root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    completion = _load_json(repo_root, _required_text(entry.get("completion_artifact"), "completion_artifact"))
    settlement = _load_json(repo_root, _required_text(entry.get("settlement_artifact"), "settlement_artifact"))
    review = _load_json(repo_root, str(entry.get("independent_review_artifact") or ""), required=False)
    invalidation = _load_json(repo_root, str(entry.get("invalidation_artifact") or ""), required=False)
    assert completion is not None and settlement is not None

    projection = _base_projection(entry, completion, settlement, review)
    projection_type = projection["projection_type"]
    unproved = _list_text(completion.get("not_proved") or completion.get("unknowns_preserved"))
    next_evidence = _list_text(completion.get("next_research_actions") or completion.get("next_research_action"))
    invalidated_evidence: dict[str, Any] | None = None

    if projection_type == "ROUND5_LOCAL_JUDGMENT_CHANGE":
        _require_equal(
            completion.get("schema_version"),
            "enterprise-judgment-round5-real-feedback-completion-receipt.v1",
            "round5_completion_schema",
        )
        _require_equal(completion.get("feedback_turn_status"), "REAL_FEEDBACK_TURN_5_COMPLETED", "round5_status")
        review_accepted = bool(
            review
            and review.get("schema_version") == "enterprise-judgment-round5-independent-postoutcome-review.v1"
            and review.get("review_id") == _mapping(completion.get("independent_review_ref")).get("review_id")
            and review.get("verdict") == "ACCEPT_LOCAL_MATERIAL_JUDGMENT_CHANGE_ONLY"
        )
        company_status = "ACCEPTED_LOCAL_FINDING" if review_accepted else "UNREVIEWED"
        company_statement = str(_mapping(completion.get("material_judgment_change")).get("investor_effect") or "")
        method_status = "NOT_EVALUATED"
        transfer_status = "NOT_EVALUATED"
        method_statement = "This round changed one issuer-level judgment boundary; it did not compare methods."
        transfer_statement = "No different-company pre-freeze application was tested in this round."
    elif projection_type == "ROUND6_CROSS_COMPANY_DEVELOPMENT_UTILITY":
        _require_equal(
            completion.get("schema_version"),
            "enterprise-judgment-round6-transfer-utility-completion.v1",
            "round6_completion_schema",
        )
        _require_equal(completion.get("status"), "ROUND6_REAL_TRANSFER_UTILITY_COMPLETED", "round6_status")
        review_accepted = bool(
            review
            and review.get("schema_version") == "enterprise-judgment-round6-transfer-utility-review.v1"
            and review.get("review_id") == completion.get("review_ref")
            and review.get("settlement_ref") == _settlement_ref(completion)
            and review.get("overall_verdict") == "ENHANCED_IMPROVED_KEY_UNKNOWN"
        )
        company_status = "ACCEPTED_BOUNDED_FINDING" if review_accepted else "UNREVIEWED"
        company_statement = str(completion.get("investor_summary") or "")
        method_status = "POSITIVE_DEVELOPMENT_UTILITY" if review_accepted else "UNREVIEWED"
        transfer_status = "DEVELOPMENT_EVIDENCE_ONLY" if review_accepted else "UNREVIEWED"
        method_statement = str(_mapping(review).get("investor_effect") or "Independent acceptance is missing.")
        transfer_statement = (
            "A prior boundary lesson was useful on a different company, but repository-memory exposure and the absence "
            "of a formal same-definition L4 chain prevent transfer validation."
            if review_accepted else "Transfer evidence cannot be elevated without independent review."
        )
    elif projection_type == "ROUND7_MULTIDIMENSIONAL_DEVELOPMENT_UTILITY":
        _require_equal(
            completion.get("schema_version"),
            "enterprise-judgment-round7-multidimensional-completion.v1",
            "round7_completion_schema",
        )
        _require_equal(completion.get("status"), "ROUND7_REAL_MULTIDIMENSIONAL_FEEDBACK_COMPLETED", "round7_status")
        review_accepted = bool(
            review
            and review.get("schema_version") == "enterprise-judgment-round7-multidimensional-review.v1"
            and review.get("review_id") == completion.get("review_ref")
            and review.get("settlement_ref") == _settlement_ref(completion)
            and review.get("overall_verdict") == "ENHANCED_MATERIALLY_IMPROVED_ENTERPRISE_JUDGMENT"
        )
        company_status = "ACCEPTED_BOUNDED_FINDING" if review_accepted else "UNREVIEWED"
        company_statement = str(completion.get("investor_summary") or "")
        method_status = "POSITIVE_DEVELOPMENT_UTILITY" if review_accepted else "UNREVIEWED"
        transfer_status = "NOT_ESTABLISHED"
        method_statement = str(_mapping(review).get("investor_effect") or "Independent acceptance is missing.")
        transfer_statement = "One company-cutoff can show development utility but cannot establish cross-company transfer."
    elif projection_type == "ROUND8_CROSS_INDUSTRY_NO_ADVANTAGE":
        _require_equal(
            completion.get("schema_version"),
            "enterprise-judgment-round8-completion.v2",
            "round8_completion_schema",
        )
        _require_equal(completion.get("status"), "ROUND8_REAL_CROSS_INDUSTRY_FEEDBACK_COMPLETED", "round8_status")
        review_accepted = bool(
            review
            and review.get("schema_version") == "enterprise-judgment-round8-independent-utility-acceptance.v2"
            and review.get("acceptance_id") == completion.get("independent_acceptance_ref")
            and review.get("settlement_ref") == _settlement_ref(completion)
            and review.get("review_status") == "SUBSTANTIVE_ACCEPTED_NO_METHOD_ADVANTAGE"
            and review.get("overall_conclusion") == "REAL_FEEDBACK_COMPLETED_NO_MATERIAL_METHOD_ADVANTAGE_PROVED"
        )
        company_status = "ACCEPTED_BOUNDED_FINDING" if review_accepted else "UNREVIEWED"
        company_statement = " ".join(_list_text(completion.get("proved"))[:4])
        method_status = "NO_ADVANTAGE_PROVED" if review_accepted else "UNREVIEWED"
        transfer_status = "NOT_ESTABLISHED"
        method_statement = (
            "The cross-industry comparison is valid negative evidence: it did not prove a material advantage for the enhanced method."
            if review_accepted else "Method utility cannot be elevated without independent acceptance."
        )
        transfer_statement = "A valid no-advantage result cannot be promoted into method transfer."
    else:
        _require_equal(
            completion.get("schema_version"),
            "enterprise-judgment-round9-outcome-closeout.v1",
            "round9_completion_schema",
        )
        _require_equal(
            completion.get("status"),
            "ROUND9_OUTCOME_SETTLED_METHOD_COMPARISON_INVALID",
            "round9_status",
        )
        if invalidation is None:
            raise LearningReadModelError("round9_invalidation_missing")
        _require_equal(
            invalidation.get("schema_version"),
            "enterprise-judgment-method-feedback-invalidation.v1",
            "round9_invalidation_schema",
        )
        _require_equal(invalidation.get("status"), "METHOD_COMPARISON_INVALID_MODEL_ERROR", "round9_invalidation_status")
        review_confirms_rejection = bool(
            review
            and review.get("schema_version") == "enterprise-judgment-round9-external-postoutcome-review.v1"
            and review.get("review_id") == completion.get("independent_review_ref")
            and review.get("settlement_ref") == _settlement_ref(completion)
            and review.get("outcome_settlement_status") == "ACCEPTED"
            and review.get("method_feedback_status") == "REJECTED_MODEL_ERROR"
        )
        company_status = "ACCEPTED_OUTCOME_FINDING" if review_confirms_rejection else "UNREVIEWED"
        company_statement = " ".join(_list_text(completion.get("proved")))
        method_status = "INVALIDATED" if review_confirms_rejection else "INVALIDATED_PENDING_EXTERNAL_REVIEW"
        transfer_status = "INVALIDATED"
        method_statement = str(invalidation.get("economic_impact") or "")
        transfer_statement = "The invalid comparison contributes no method or transfer evidence."
        invalidated_evidence = {
            "status": method_status,
            "root_causes": deepcopy(_items(invalidation.get("root_causes"))),
            "prohibited_claims": deepcopy(_items(invalidation.get("prohibited_claims"))),
            "remediation": str(invalidation.get("remediation") or ""),
        }
        unproved = _list_text(completion.get("not_proved"))

    projection.update({
        "company_finding": {
            "status": company_status,
            "statement": company_statement,
        },
        "measurement_learning": {
            "status": "SUPPORTED",
            "statement": "Observed fields remain usable while UNKNOWN and MEASUREMENT_MISMATCH stay in the denominator.",
        },
        "method_utility": {
            "status": method_status,
            "statement": method_statement,
        },
        "transfer_evidence": {
            "status": transfer_status,
            "statement": transfer_statement,
        },
        "invalidated_evidence": invalidated_evidence,
        "what_remains_unproved": unproved,
        "next_evidence": next_evidence,
    })
    return projection


def _aggregate_denominators(entries: list[dict[str, Any]], field: str) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    total = 0
    for entry in entries:
        denominator = _mapping(entry.get(field))
        total += int(denominator.get("total_cells") or denominator.get("total_findings") or 0)
        for status, count in _mapping(denominator.get("status_counts")).items():
            counts[str(status)] += int(count)
    return {"total": total, "status_counts": dict(sorted(counts.items()))}


def build_learning_read_model(
    manifest: dict[str, Any],
    *,
    repo_root: str | Path,
    manifest_ref: str = "",
) -> dict[str, Any]:
    """Build the current learning status from an explicit structured manifest."""
    if not isinstance(manifest, dict):
        raise LearningReadModelError("manifest_not_object")
    _require_equal(manifest.get("schema_version"), MANIFEST_SCHEMA_VERSION, "manifest_schema_version")
    as_of = _required_text(manifest.get("as_of"), "as_of")
    protocol_refs = _list_text(manifest.get("protocol_refs"))
    if not protocol_refs:
        raise LearningReadModelError("protocol_refs_missing")
    source_entries = _items(manifest.get("entries"))
    if not source_entries:
        raise LearningReadModelError("manifest_entries_missing")
    round_ids = [_required_text(_mapping(item).get("round_id"), "round_id") for item in source_entries]
    if len(round_ids) != len(set(round_ids)):
        raise LearningReadModelError("duplicate_round_id")

    root = Path(repo_root)
    entries = [_project_entry(root, _mapping(item)) for item in source_entries]
    method_statuses = Counter(str(_mapping(item.get("method_utility")).get("status")) for item in entries)
    transfer_statuses = Counter(str(_mapping(item.get("transfer_evidence")).get("status")) for item in entries)
    rights = {right: "NOT_AUTHORIZED" for right in DOWNSTREAM_RIGHTS}

    levels = [
        {"level": "K0", "status": "AVAILABLE", "definition": LEVEL_DEFINITIONS["K0"],
         "basis": "The manifest points to industry-block training receipts and bounded investor findings."},
        {"level": "L0", "status": "SUBSTANTIATED_FOR_RECORDED_EPISODES", "definition": LEVEL_DEFINITIONS["L0"],
         "basis": "All projected entries preserve closed rights and explicit unresolved outcomes."},
        {"level": "L1", "status": "SUBSTANTIATED_FOR_RECORDED_EPISODES", "definition": LEVEL_DEFINITIONS["L1"],
         "basis": f"{len(entries)} company-cutoff settlements contain structured cell-level outcomes."},
        {"level": "L2", "status": "NOT_ESTABLISHED", "definition": LEVEL_DEFINITIONS["L2"],
         "basis": "No accepted same-pair A_ONLY/B_ONLY/MIXED/NOT_DIAGNOSTIC receipt under an original frozen predicate is present."},
        {"level": "L3", "status": "NOT_ESTABLISHED", "definition": LEVEL_DEFINITIONS["L3"],
         "basis": "No accepted SELECTION_ADMITTED primary-path episode versus a fair baseline is present."},
        {"level": "L4", "status": "NOT_ESTABLISHED_DEVELOPMENT_EVIDENCE_PRESENT", "definition": LEVEL_DEFINITIONS["L4"],
         "basis": "Round 6 shows bounded cross-company utility, but not a formal same-definition learning-note application chain."},
        {"level": "L5", "status": "NOT_ESTABLISHED", "definition": LEVEL_DEFINITIONS["L5"],
         "basis": "There are no multiple independent accepted L3 episodes under a frozen cohort aggregation plan."},
    ]

    return {
        "schema_version": READ_MODEL_SCHEMA_VERSION,
        "as_of": as_of,
        "manifest_ref": str(manifest_ref or ""),
        "protocol_refs": protocol_refs,
        "purpose": "Separate completed pipeline work from evidence that investor judgment or method transfer improved.",
        "current_ceiling": {
            "strict_validation_level": "L1",
            "investor_statement": (
                "Turtle can repeatedly obtain and settle real company outcomes, and it has produced bounded company and "
                "development-method findings. It has not yet proved a diagnostic mechanism choice, transferable judgment "
                "method, or relative method advantage."
            ),
            "next_unmet_level": "L2",
            "evidence_needed": [
                "One frozen mechanism pair with distinct outcome predicates and an independently accepted diagnostic verdict.",
                "UNKNOWN, MIXED, NOT_DIAGNOSTIC and MEASUREMENT_MISMATCH retained without replacement.",
                "No use of the same settled outcome to repair and re-credit a method rule.",
            ],
        },
        "validation_ladder": levels,
        "evidence_inventory": entries,
        "evidence_counts": {
            "recorded_company_cutoff_settlements": len(entries),
            "method_utility_statuses": dict(sorted(method_statuses.items())),
            "transfer_evidence_statuses": dict(sorted(transfer_statuses.items())),
        },
        "preserved_denominator": {
            "measurement_cells": _aggregate_denominators(entries, "measurement_denominator"),
            "diagnostic_findings": _aggregate_denominators(entries, "diagnostic_denominator"),
        },
        "investor_readout": {
            "proved": [
                "Real official outcome fields can be settled without forcing missing or mismatched fields into labels.",
                "Several bounded company findings changed what an investor should and should not credit to management.",
                "Round 6 and Round 7 provide positive development utility, while Round 8 honestly records no proved advantage.",
                "Round 9 outcome facts survive even though its method comparison is invalidated.",
            ],
            "not_proved": [
                "A selected enterprise mechanism has passed formal L2/L3 validation.",
                "The eight-dimensional method transfers reliably across companies or industries.",
                "The training evidence may alter CJO, valuation, reports, buy bands or investment actions.",
            ],
            "next_decisive_step": (
                "Complete one clean L2 mechanism-pair settlement, then use its accepted lesson in a different pre-outcome "
                "company episode before attempting L4 or any multi-episode L5 comparison."
            ),
        },
        "rights": rights,
        "aggregation_policy": "COUNTS_AND_EVIDENCE_CLASSES_ONLY_NO_TOTAL_RANKING",
    }


def validate_learning_read_model(read_model: dict[str, Any]) -> dict[str, Any]:
    """Validate the few invariants that make this read model safe to consume."""
    findings: list[str] = []
    if not isinstance(read_model, dict):
        return {"valid": False, "findings": ["read_model_not_object"]}
    if read_model.get("schema_version") != READ_MODEL_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    if _mapping(read_model.get("current_ceiling")).get("strict_validation_level") != "L1":
        findings.append("current_ceiling_invalid")
    if any(right != "NOT_AUTHORIZED" for right in _mapping(read_model.get("rights")).values()):
        findings.append("downstream_right_open")
    for entry in _items(read_model.get("evidence_inventory")):
        row = _mapping(entry)
        if row.get("strict_level_ceiling") != "L1":
            findings.append("entry_level_elevated:" + str(row.get("round_id") or "UNKNOWN"))
        method_status = _mapping(row.get("method_utility")).get("status")
        if row.get("round_id") == "ROUND8" and method_status not in {"NO_ADVANTAGE_PROVED", "UNREVIEWED"}:
            findings.append("round8_method_status_invalid")
        if row.get("round_id") == "ROUND9" and not str(method_status).startswith("INVALIDATED"):
            findings.append("round9_method_status_invalid")
    return {"valid": not findings, "findings": findings}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Structured input manifest relative to --repo-root or absolute.")
    parser.add_argument("--repo-root", default=".", help="Repository root used to resolve artifact references.")
    parser.add_argument("--output", help="Write the read model to this path; stdout when omitted.")
    parser.add_argument("--check-only", action="store_true", help="Build and validate without writing output.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = Path(args.repo_root).resolve()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        manifest_ref = str(manifest_path.relative_to(root))
    except ValueError:
        manifest_ref = str(manifest_path)
    read_model = build_learning_read_model(manifest, repo_root=root, manifest_ref=manifest_ref)
    validation = validate_learning_read_model(read_model)
    if not validation["valid"]:
        raise LearningReadModelError("read_model_invalid:" + ",".join(validation["findings"]))
    if not args.check_only:
        payload = json.dumps(read_model, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            output_path = Path(args.output)
            if not output_path.is_absolute():
                output_path = root / output_path
            output_path.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
