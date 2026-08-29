#!/usr/bin/env python3
"""Review the investment utility of an IndustryUnderwritingContext A/B pair.

The reviewer compares frozen treatment snapshots, not prose quality.  A richer
industry explanation is useful context but earns ``MATERIAL_UTILITY`` only
when it changes a material investment/research treatment or strictly narrows a
like-for-like key economic range.  Local ``UNKNOWN`` and ``BOUNDED`` states
remain reviewable and never block unrelated dimensions.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping


SNAPSHOT_SCHEMA_VERSION = "industry-underwriting-treatment.v1"
REVIEW_SCHEMA_VERSION = "industry-underwriting-utility-review.v1"
VALIDATION_SCHEMA_VERSION = "industry-underwriting-utility-review-validation.v1"

DIMENSIONS = (
    "industry_future_path",
    "target_exposure",
    "owner_cash_treatment",
    "permanent_loss_path",
    "valuation_route_and_required_evidence",
)
DIMENSION_IDS = {
    "industry_future_path": "INDUSTRY_FUTURE_PATH",
    "target_exposure": "TARGET_EXPOSURE",
    "owner_cash_treatment": "OWNER_CASH_TREATMENT",
    "permanent_loss_path": "PERMANENT_LOSS_PATH",
    "valuation_route_and_required_evidence": "VALUATION_ROUTE_AND_REQUIRED_EVIDENCE",
}
STATUSES = {"READY", "BOUNDED", "UNKNOWN"}
DIRECTIONS = {"POSITIVE", "NEUTRAL", "NEGATIVE", "MIXED", "CONDITIONAL", "UNKNOWN"}
BASE_CASE_ROLES = {
    "INCLUDE", "INCLUDE_CONDITIONALLY", "SCENARIO_ONLY", "EXCLUDE", "UNRESOLVED",
}
DECISION_ACTIONS = {
    "PROCEED", "PROCEED_WITH_HAIRCUT", "WAIT_FOR_DECISIVE_EVIDENCE",
    "REJECT", "NO_ACTION_CHANGE", "UNRESOLVED",
}
EVIDENCE_PRIORITIES = {"DECISIVE", "SUPPORTING"}
UTILITY_VERDICTS = {"MATERIAL_UTILITY", "NO_MATERIAL_UTILITY"}

_SNAPSHOT_KEYS = {
    "schema_version", "snapshot_id", "company_id", "cutoff_at", "status", "dimensions",
}
_AXIS_KEYS = {
    "status", "thesis_code", "direction", "investment_treatment",
    "key_economic_range", "required_evidence", "explanation",
}
_TREATMENT_KEYS = {"base_case_role", "decision_action", "reason"}
_RANGE_KEYS = {"metric", "scope", "unit", "lower", "upper"}
_EVIDENCE_KEYS = {"evidence_id", "priority"}
_REVIEW_KEYS = {
    "schema_version", "review_id", "company_id", "cutoff_at", "reviewed_at",
    "context_status", "baseline_treatment", "context_informed_treatment",
    "dimension_reviews", "utility_verdict", "utility_basis",
    "material_treatment_change_dimensions", "narrowed_range_dimensions",
    "explanation_only_dimensions", "nonqualifying_change_dimensions",
    "non_blocking_unknown_dimensions", "investor_conclusion", "review_policy",
}


class IndustryUnderwritingUtilityReviewError(ValueError):
    """The A/B snapshots cannot be compared under the v1 contract."""

    def __init__(self, findings: list[str]):
        self.findings = list(dict.fromkeys(findings))
        super().__init__("industry_underwriting_utility_review_invalid:" + ";".join(self.findings))


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _closed(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        findings.append(f"{path}_must_be_object")
    for key in sorted(set(item).difference(allowed)):
        findings.append(f"{path}_contains_unapproved_field:{key}")
    for key in sorted(allowed.difference(item)):
        findings.append(f"{path}_missing_required_field:{key}")
    return item


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        findings.append(f"{path}_must_be_timezone_aware_iso8601")
        return None
    return parsed.astimezone(timezone.utc)


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validate_range(value: Any, path: str, findings: list[str]) -> None:
    if value is None:
        return
    item = _closed(value, _RANGE_KEYS, path, findings)
    for field in ("metric", "scope", "unit"):
        if not _text(item.get(field)):
            findings.append(f"{path}.{field}_required")
    lower, upper = item.get("lower"), item.get("upper")
    if not _number(lower) or not _number(upper):
        findings.append(f"{path}.bounds_must_be_finite_numbers")
    elif float(lower) > float(upper):
        findings.append(f"{path}.lower_must_not_exceed_upper")


def _validate_axis(value: Any, path: str, findings: list[str]) -> None:
    axis = _closed(value, _AXIS_KEYS, path, findings)
    if axis.get("status") not in STATUSES:
        findings.append(f"{path}.status_invalid")
    if not _text(axis.get("thesis_code")):
        findings.append(f"{path}.thesis_code_required")
    if axis.get("direction") not in DIRECTIONS:
        findings.append(f"{path}.direction_invalid")
    if not _text(axis.get("explanation")):
        findings.append(f"{path}.explanation_required")

    treatment = _closed(
        axis.get("investment_treatment"), _TREATMENT_KEYS,
        f"{path}.investment_treatment", findings,
    )
    if treatment.get("base_case_role") not in BASE_CASE_ROLES:
        findings.append(f"{path}.investment_treatment.base_case_role_invalid")
    if treatment.get("decision_action") not in DECISION_ACTIONS:
        findings.append(f"{path}.investment_treatment.decision_action_invalid")
    if not _text(treatment.get("reason")):
        findings.append(f"{path}.investment_treatment.reason_required")

    _validate_range(axis.get("key_economic_range"), f"{path}.key_economic_range", findings)
    evidence = axis.get("required_evidence")
    if not isinstance(evidence, list):
        findings.append(f"{path}.required_evidence_must_be_array")
    seen: set[str] = set()
    for index, raw in enumerate(_items(evidence)):
        item_path = f"{path}.required_evidence[{index}]"
        item = _closed(raw, _EVIDENCE_KEYS, item_path, findings)
        evidence_id = item.get("evidence_id")
        if not _text(evidence_id) or evidence_id in seen:
            findings.append(f"{item_path}.evidence_id_invalid_or_duplicate")
        seen.add(str(evidence_id))
        if item.get("priority") not in EVIDENCE_PRIORITIES:
            findings.append(f"{item_path}.priority_invalid")

    if axis.get("status") == "UNKNOWN" and (
        axis.get("direction") != "UNKNOWN"
        or treatment.get("base_case_role") != "UNRESOLVED"
        or treatment.get("decision_action") != "UNRESOLVED"
        or axis.get("key_economic_range") is not None
    ):
        findings.append(f"{path}.unknown_state_must_not_claim_resolved_treatment_or_range")


def _snapshot_findings(value: Any, path: str) -> list[str]:
    findings: list[str] = []
    snapshot = _closed(value, _SNAPSHOT_KEYS, path, findings)
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        findings.append(f"{path}.schema_version_invalid")
    for field in ("snapshot_id", "company_id"):
        if not _text(snapshot.get(field)):
            findings.append(f"{path}.{field}_required")
    _instant(snapshot.get("cutoff_at"), f"{path}.cutoff_at", findings)
    if snapshot.get("status") not in STATUSES:
        findings.append(f"{path}.status_invalid")

    dimensions = _closed(snapshot.get("dimensions"), set(DIMENSIONS), f"{path}.dimensions", findings)
    for dimension in DIMENSIONS:
        _validate_axis(dimensions.get(dimension), f"{path}.dimensions.{dimension}", findings)

    axis_statuses = [_mapping(dimensions.get(dimension)).get("status") for dimension in DIMENSIONS]
    if snapshot.get("status") == "READY" and "UNKNOWN" in axis_statuses:
        findings.append(f"{path}.ready_snapshot_cannot_contain_unknown_dimension")
    if snapshot.get("status") == "UNKNOWN" and any(status != "UNKNOWN" for status in axis_statuses):
        findings.append(f"{path}.unknown_snapshot_requires_all_dimensions_unknown")
    return list(dict.fromkeys(findings))


def validate_treatment_snapshot(value: Any) -> dict[str, Any]:
    """Validate one frozen baseline or context-informed treatment snapshot."""
    findings = _snapshot_findings(value, "treatment_snapshot")
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "valid": not findings,
        "findings": findings,
    }


def _evidence_signature(axis: Mapping[str, Any], priority: str | None = None) -> tuple[tuple[str, str], ...]:
    rows = []
    for raw in _items(axis.get("required_evidence")):
        item = _mapping(raw)
        if priority is None or item.get("priority") == priority:
            rows.append((str(item.get("evidence_id")), str(item.get("priority"))))
    return tuple(sorted(rows))


def _range_narrowed(baseline: Any, informed: Any) -> bool:
    before, after = _mapping(baseline), _mapping(informed)
    if not before or not after:
        return False
    identity = ("metric", "scope", "unit")
    if any(before.get(field) != after.get(field) for field in identity):
        return False
    if not all(_number(item.get(bound)) for item in (before, after) for bound in ("lower", "upper")):
        return False
    before_lower = Decimal(str(before["lower"]))
    before_upper = Decimal(str(before["upper"]))
    after_lower = Decimal(str(after["lower"]))
    after_upper = Decimal(str(after["upper"]))
    return (
        after_lower >= before_lower
        and after_upper <= before_upper
        and after_upper - after_lower < before_upper - before_lower
    )


def _changed_fields(baseline: Mapping[str, Any], informed: Mapping[str, Any]) -> list[str]:
    fields: list[str] = []
    for field in ("status", "thesis_code", "direction", "explanation"):
        if baseline.get(field) != informed.get(field):
            fields.append(field)
    before_treatment = _mapping(baseline.get("investment_treatment"))
    after_treatment = _mapping(informed.get("investment_treatment"))
    for field in ("base_case_role", "decision_action", "reason"):
        if before_treatment.get(field) != after_treatment.get(field):
            fields.append(f"investment_treatment.{field}")
    if baseline.get("key_economic_range") != informed.get("key_economic_range"):
        fields.append("key_economic_range")
    if _evidence_signature(baseline) != _evidence_signature(informed):
        fields.append("required_evidence")
    return fields


def _dimension_review(
    dimension: str,
    baseline: Mapping[str, Any],
    informed: Mapping[str, Any],
) -> dict[str, Any]:
    changed_fields = _changed_fields(baseline, informed)
    reasons: list[str] = []
    before_treatment = _mapping(baseline.get("investment_treatment"))
    after_treatment = _mapping(informed.get("investment_treatment"))
    if before_treatment.get("base_case_role") != after_treatment.get("base_case_role"):
        reasons.append("BASE_CASE_ROLE_CHANGED")
    if before_treatment.get("decision_action") != after_treatment.get("decision_action"):
        reasons.append("DECISION_ACTION_CHANGED")
    if dimension == "valuation_route_and_required_evidence":
        if baseline.get("thesis_code") != informed.get("thesis_code"):
            reasons.append("VALUATION_ROUTE_CHANGED")
        if _evidence_signature(baseline, "DECISIVE") != _evidence_signature(informed, "DECISIVE"):
            reasons.append("DECISIVE_REQUIRED_EVIDENCE_CHANGED")

    narrowed = _range_narrowed(
        baseline.get("key_economic_range"), informed.get("key_economic_range")
    )
    material_treatment_changed = bool(reasons)
    qualifies = material_treatment_changed or narrowed
    unknown = baseline.get("status") == "UNKNOWN" or informed.get("status") == "UNKNOWN"
    explanation_only_fields = {
        "status", "thesis_code", "direction", "explanation",
        "investment_treatment.reason", "required_evidence",
    }
    explanation_only = bool(changed_fields) and not qualifies and set(changed_fields).issubset(
        explanation_only_fields
    )
    if qualifies:
        comparison_status = "QUALIFYING_MATERIAL_CHANGE"
    elif not changed_fields and unknown:
        comparison_status = "UNRESOLVED_NON_BLOCKING"
    elif not changed_fields:
        comparison_status = "NO_CHANGE"
    elif explanation_only:
        comparison_status = "EXPLANATION_ONLY"
    else:
        comparison_status = "NONQUALIFYING_CHANGE"
    return {
        "dimension_id": DIMENSION_IDS[dimension],
        "baseline_status": baseline.get("status"),
        "context_informed_status": informed.get("status"),
        "changed_fields": changed_fields,
        "material_treatment_changed": material_treatment_changed,
        "key_economic_range_narrowed": narrowed,
        "qualifying_reasons": reasons + (["KEY_ECONOMIC_RANGE_NARROWED"] if narrowed else []),
        "comparison_status": comparison_status,
    }


def _build_review(
    baseline: dict[str, Any],
    informed: dict[str, Any],
    *,
    review_id: str,
    reviewed_at: str,
) -> dict[str, Any]:
    baseline_dimensions = _mapping(baseline["dimensions"])
    informed_dimensions = _mapping(informed["dimensions"])
    reviews = [
        _dimension_review(
            dimension,
            _mapping(baseline_dimensions[dimension]),
            _mapping(informed_dimensions[dimension]),
        )
        for dimension in DIMENSIONS
    ]
    material_dimensions = [
        item["dimension_id"] for item in reviews if item["material_treatment_changed"]
    ]
    narrowed_dimensions = [
        item["dimension_id"] for item in reviews if item["key_economic_range_narrowed"]
    ]
    explanation_dimensions = [
        item["dimension_id"] for item in reviews if item["comparison_status"] == "EXPLANATION_ONLY"
    ]
    nonqualifying_dimensions = [
        item["dimension_id"] for item in reviews
        if item["comparison_status"] == "NONQUALIFYING_CHANGE"
    ]
    unknown_dimensions = [
        item["dimension_id"] for item in reviews
        if "UNKNOWN" in {item["baseline_status"], item["context_informed_status"]}
    ]
    verdict = (
        "MATERIAL_UTILITY" if material_dimensions or narrowed_dimensions
        else "NO_MATERIAL_UTILITY"
    )
    utility_basis = [
        {
            "dimension_id": item["dimension_id"],
            "qualifying_reasons": item["qualifying_reasons"],
        }
        for item in reviews if item["qualifying_reasons"]
    ]
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "review_id": review_id,
        "company_id": baseline["company_id"],
        "cutoff_at": baseline["cutoff_at"],
        "reviewed_at": reviewed_at,
        "context_status": informed["status"],
        "baseline_treatment": deepcopy(baseline),
        "context_informed_treatment": deepcopy(informed),
        "dimension_reviews": reviews,
        "utility_verdict": verdict,
        "utility_basis": utility_basis,
        "material_treatment_change_dimensions": material_dimensions,
        "narrowed_range_dimensions": narrowed_dimensions,
        "explanation_only_dimensions": explanation_dimensions,
        "nonqualifying_change_dimensions": nonqualifying_dimensions,
        "non_blocking_unknown_dimensions": unknown_dimensions,
        "investor_conclusion": (
            "CONTEXT_CHANGED_MATERIAL_TREATMENT_OR_NARROWED_KEY_RANGE"
            if verdict == "MATERIAL_UTILITY"
            else "CONTEXT_ADDED_NO_QUALIFYING_INVESTMENT_UTILITY"
        ),
        "review_policy": {
            "materiality_rule": (
                "MATERIAL_TREATMENT_CHANGE_OR_LIKE_FOR_LIKE_KEY_ECONOMIC_RANGE_NARROWING"
            ),
            "explanation_only_never_qualifies": True,
            "unknown_and_bounded_are_non_blocking": True,
            "verdict_is_mechanically_derived": True,
        },
    }


def review_industry_underwriting_utility(
    baseline_treatment: Mapping[str, Any],
    context_informed_treatment: Mapping[str, Any],
    *,
    review_id: str | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    """Compare a same-company, same-cutoff baseline/context treatment pair."""
    baseline = deepcopy(dict(baseline_treatment)) if isinstance(baseline_treatment, Mapping) else {}
    informed = (
        deepcopy(dict(context_informed_treatment))
        if isinstance(context_informed_treatment, Mapping) else {}
    )
    findings = [
        *_snapshot_findings(baseline_treatment, "baseline_treatment"),
        *_snapshot_findings(context_informed_treatment, "context_informed_treatment"),
    ]
    if baseline.get("company_id") != informed.get("company_id"):
        findings.append("treatment_pair.company_id_must_match")
    if baseline.get("cutoff_at") != informed.get("cutoff_at"):
        findings.append("treatment_pair.cutoff_at_must_match")
    if baseline.get("snapshot_id") == informed.get("snapshot_id"):
        findings.append("treatment_pair.snapshot_ids_must_differ")
    resolved_review_id = review_id or (
        f"IUR:{baseline.get('company_id', 'UNKNOWN')}:{baseline.get('cutoff_at', 'UNKNOWN')}:V1"
    )
    if not _text(resolved_review_id):
        findings.append("treatment_pair.review_id_required")
    resolved_reviewed_at = reviewed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    _instant(resolved_reviewed_at, "treatment_pair.reviewed_at", findings)
    if findings:
        raise IndustryUnderwritingUtilityReviewError(findings)
    return _build_review(
        baseline, informed,
        review_id=str(resolved_review_id), reviewed_at=str(resolved_reviewed_at),
    )


def validate_industry_underwriting_utility_review(value: Any) -> dict[str, Any]:
    """Validate a persisted review and recompute every derived verdict field."""
    findings: list[str] = []
    review = _closed(value, _REVIEW_KEYS, "industry_underwriting_utility_review", findings)
    if review.get("schema_version") != REVIEW_SCHEMA_VERSION:
        findings.append("industry_underwriting_utility_review.schema_version_invalid")
    if not _text(review.get("review_id")):
        findings.append("industry_underwriting_utility_review.review_id_required")
    _instant(review.get("cutoff_at"), "industry_underwriting_utility_review.cutoff_at", findings)
    _instant(review.get("reviewed_at"), "industry_underwriting_utility_review.reviewed_at", findings)
    findings.extend(_snapshot_findings(review.get("baseline_treatment"), "baseline_treatment"))
    findings.extend(
        _snapshot_findings(review.get("context_informed_treatment"), "context_informed_treatment")
    )
    baseline = _mapping(review.get("baseline_treatment"))
    informed = _mapping(review.get("context_informed_treatment"))
    if baseline and informed:
        if baseline.get("snapshot_id") == informed.get("snapshot_id"):
            findings.append("industry_underwriting_utility_review.snapshot_ids_must_differ")
        if review.get("company_id") != baseline.get("company_id") or baseline.get("company_id") != informed.get("company_id"):
            findings.append("industry_underwriting_utility_review.company_id_binding_invalid")
        if review.get("cutoff_at") != baseline.get("cutoff_at") or baseline.get("cutoff_at") != informed.get("cutoff_at"):
            findings.append("industry_underwriting_utility_review.cutoff_at_binding_invalid")
        if review.get("context_status") != informed.get("status"):
            findings.append("industry_underwriting_utility_review.context_status_binding_invalid")
    if not findings:
        expected = _build_review(
            baseline, informed,
            review_id=str(review["review_id"]), reviewed_at=str(review["reviewed_at"]),
        )
        for field in sorted(_REVIEW_KEYS):
            if review.get(field) != expected.get(field):
                findings.append(f"industry_underwriting_utility_review.{field}_not_mechanically_derived")
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "valid": not findings,
        "findings": list(dict.fromkeys(findings)),
        "utility_verdict": review.get("utility_verdict") if not findings else None,
    }


def _read_json(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndustryUnderwritingUtilityReviewError([f"input_unreadable:{path}:{exc}"]) from exc
    if not isinstance(value, dict):
        raise IndustryUnderwritingUtilityReviewError([f"input_must_be_json_object:{path}"])
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare baseline and IndustryUnderwritingContext-informed treatments.",
    )
    parser.add_argument("--baseline", required=True, help="Baseline treatment JSON file")
    parser.add_argument(
        "--context-informed", required=True, dest="context_informed",
        help="Context-informed treatment JSON file",
    )
    parser.add_argument("--review-id")
    parser.add_argument("--reviewed-at", help="Timezone-aware ISO-8601 review time")
    parser.add_argument("--output", help="Write the review JSON here; stdout when omitted")
    args = parser.parse_args(argv)
    try:
        review = review_industry_underwriting_utility(
            _read_json(args.baseline),
            _read_json(args.context_informed),
            review_id=args.review_id,
            reviewed_at=args.reviewed_at,
        )
    except IndustryUnderwritingUtilityReviewError as exc:
        print(json.dumps({"valid": False, "findings": exc.findings}, ensure_ascii=False), file=sys.stderr)
        return 2
    rendered = json.dumps(review, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
