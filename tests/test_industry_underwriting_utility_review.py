from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import industry_underwriting_utility_review as utility


REVIEWED_AT = "2026-08-29T09:00:00+00:00"


def _axis(
    code: str,
    *,
    status: str = "READY",
    direction: str = "NEUTRAL",
    base_case_role: str = "INCLUDE",
    decision_action: str = "NO_ACTION_CHANGE",
    economic_range: dict | None = None,
    required_evidence: list[dict] | None = None,
    explanation: str = "Frozen same-cutoff treatment.",
) -> dict:
    if status == "UNKNOWN":
        direction = "UNKNOWN"
        base_case_role = "UNRESOLVED"
        decision_action = "UNRESOLVED"
        economic_range = None
    return {
        "status": status,
        "thesis_code": code,
        "direction": direction,
        "investment_treatment": {
            "base_case_role": base_case_role,
            "decision_action": decision_action,
            "reason": "Frozen investment treatment.",
        },
        "key_economic_range": economic_range,
        "required_evidence": required_evidence or [],
        "explanation": explanation,
    }


def _snapshot(snapshot_id: str, *, status: str = "READY") -> dict:
    dimensions = {
        "industry_future_path": _axis("PATH:STABLE"),
        "target_exposure": _axis("EXPOSURE:NEUTRAL"),
        "owner_cash_treatment": _axis(
            "OWNER_CASH:REPORTED_PROXY",
            economic_range={
                "metric": "normalized_owner_cash_margin",
                "scope": "listed_parent_ordinary_shareholders",
                "unit": "percent",
                "lower": 5.0,
                "upper": 15.0,
            },
        ),
        "permanent_loss_path": _axis("LOSS:LOW"),
        "valuation_route_and_required_evidence": _axis(
            "ROUTE:DCF",
            required_evidence=[{"evidence_id": "E:FCFF", "priority": "DECISIVE"}],
        ),
    }
    if status == "UNKNOWN":
        dimensions = {
            name: _axis(f"UNKNOWN:{name}", status="UNKNOWN")
            for name in utility.DIMENSIONS
        }
    return {
        "schema_version": utility.SNAPSHOT_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "company_id": "HK:02669",
        "cutoff_at": "2025-03-31T00:00:00+00:00",
        "status": status,
        "dimensions": dimensions,
    }


def _review(baseline: dict, informed: dict) -> dict:
    return utility.review_industry_underwriting_utility(
        baseline,
        informed,
        review_id="IUR:HK02669:20250331:V1",
        reviewed_at=REVIEWED_AT,
    )


def _dimension(review: dict, dimension_id: str) -> dict:
    return next(row for row in review["dimension_reviews"] if row["dimension_id"] == dimension_id)


def test_material_owner_cash_treatment_change_qualifies_without_text_scoring() -> None:
    baseline = _snapshot("BASELINE")
    informed = _snapshot("CONTEXT")
    informed["dimensions"]["owner_cash_treatment"]["investment_treatment"].update({
        "base_case_role": "INCLUDE_CONDITIONALLY",
        "decision_action": "PROCEED_WITH_HAIRCUT",
        "reason": "Customer concentration makes the reported proxy conditional.",
    })

    review = _review(baseline, informed)

    assert review["utility_verdict"] == "MATERIAL_UTILITY"
    assert review["material_treatment_change_dimensions"] == ["OWNER_CASH_TREATMENT"]
    owner_cash = _dimension(review, "OWNER_CASH_TREATMENT")
    assert owner_cash["qualifying_reasons"] == [
        "BASE_CASE_ROLE_CHANGED", "DECISION_ACTION_CHANGED",
    ]
    assert utility.validate_industry_underwriting_utility_review(review)["valid"]


def test_more_industry_explanation_and_a_new_direction_are_not_material_utility() -> None:
    baseline = _snapshot("BASELINE")
    informed = _snapshot("CONTEXT")
    path = informed["dimensions"]["industry_future_path"]
    path.update({
        "thesis_code": "PATH:STRUCTURAL_POLARIZATION",
        "direction": "CONDITIONAL",
        "explanation": "A longer mechanism narrative with epochs, peers and a rival path.",
    })
    path["investment_treatment"]["reason"] = "More detailed explanation; same treatment."

    review = _review(baseline, informed)

    assert review["utility_verdict"] == "NO_MATERIAL_UTILITY"
    assert review["material_treatment_change_dimensions"] == []
    assert review["narrowed_range_dimensions"] == []
    assert review["explanation_only_dimensions"] == ["INDUSTRY_FUTURE_PATH"]
    assert _dimension(review, "INDUSTRY_FUTURE_PATH")["comparison_status"] == "EXPLANATION_ONLY"


def test_like_for_like_key_economic_range_narrowing_qualifies() -> None:
    baseline = _snapshot("BASELINE")
    informed = _snapshot("CONTEXT")
    informed["dimensions"]["owner_cash_treatment"]["key_economic_range"].update({
        "lower": 8.0,
        "upper": 12.0,
    })

    review = _review(baseline, informed)

    assert review["utility_verdict"] == "MATERIAL_UTILITY"
    assert review["material_treatment_change_dimensions"] == []
    assert review["narrowed_range_dimensions"] == ["OWNER_CASH_TREATMENT"]
    assert _dimension(review, "OWNER_CASH_TREATMENT")["qualifying_reasons"] == [
        "KEY_ECONOMIC_RANGE_NARROWED"
    ]


@pytest.mark.parametrize(
    "changed_range",
    [
        {"lower": 0.0, "upper": 20.0},
        {"lower": 8.0, "upper": 18.0},
        {"lower": 8.0, "upper": 12.0, "unit": "basis_points"},
    ],
)
def test_wider_shifted_or_different_identity_range_does_not_qualify(changed_range: dict) -> None:
    baseline = _snapshot("BASELINE")
    informed = _snapshot("CONTEXT")
    informed["dimensions"]["owner_cash_treatment"]["key_economic_range"].update(changed_range)

    review = _review(baseline, informed)

    assert review["utility_verdict"] == "NO_MATERIAL_UTILITY"
    assert review["narrowed_range_dimensions"] == []
    assert review["nonqualifying_change_dimensions"] == ["OWNER_CASH_TREATMENT"]


def test_valuation_route_or_decisive_evidence_changes_are_material_research_treatments() -> None:
    baseline = _snapshot("BASELINE")
    route_change = _snapshot("CONTEXT:ROUTE")
    route_change["dimensions"]["valuation_route_and_required_evidence"]["thesis_code"] = "ROUTE:DDM"
    route_review = _review(baseline, route_change)
    assert route_review["utility_verdict"] == "MATERIAL_UTILITY"
    assert _dimension(route_review, "VALUATION_ROUTE_AND_REQUIRED_EVIDENCE")["qualifying_reasons"] == [
        "VALUATION_ROUTE_CHANGED"
    ]

    evidence_change = _snapshot("CONTEXT:EVIDENCE")
    evidence_change["dimensions"]["valuation_route_and_required_evidence"]["required_evidence"] = [
        {"evidence_id": "E:OWNER_CASH_ACCESS", "priority": "DECISIVE"}
    ]
    evidence_review = _review(baseline, evidence_change)
    assert evidence_review["utility_verdict"] == "MATERIAL_UTILITY"
    assert _dimension(evidence_review, "VALUATION_ROUTE_AND_REQUIRED_EVIDENCE")["qualifying_reasons"] == [
        "DECISIVE_REQUIRED_EVIDENCE_CHANGED"
    ]


def test_supporting_evidence_only_is_not_material_utility() -> None:
    baseline = _snapshot("BASELINE")
    informed = _snapshot("CONTEXT")
    informed["dimensions"]["valuation_route_and_required_evidence"]["required_evidence"].append(
        {"evidence_id": "E:PEER_DESCRIPTION", "priority": "SUPPORTING"}
    )

    review = _review(baseline, informed)

    assert review["utility_verdict"] == "NO_MATERIAL_UTILITY"
    assert review["explanation_only_dimensions"] == ["VALUATION_ROUTE_AND_REQUIRED_EVIDENCE"]


def test_unknown_and_bounded_dimensions_remain_non_blocking() -> None:
    baseline = _snapshot("BASELINE", status="UNKNOWN")
    informed = deepcopy(baseline)
    informed["snapshot_id"] = "CONTEXT"

    unresolved = _review(baseline, informed)

    assert unresolved["utility_verdict"] == "NO_MATERIAL_UTILITY"
    assert unresolved["context_status"] == "UNKNOWN"
    assert unresolved["non_blocking_unknown_dimensions"] == list(utility.DIMENSION_IDS.values())
    assert all(
        item["comparison_status"] == "UNRESOLVED_NON_BLOCKING"
        for item in unresolved["dimension_reviews"]
    )
    assert utility.validate_industry_underwriting_utility_review(unresolved)["valid"]

    bounded = _snapshot("CONTEXT:BOUNDED", status="BOUNDED")
    bounded["dimensions"]["target_exposure"] = _axis("UNKNOWN:TARGET", status="UNKNOWN")
    baseline_ready = _snapshot("BASELINE:READY")
    bounded["dimensions"]["permanent_loss_path"]["investment_treatment"].update({
        "base_case_role": "SCENARIO_ONLY",
        "decision_action": "PROCEED_WITH_HAIRCUT",
        "reason": "A bounded loss path changes downside treatment.",
    })
    mixed_review = _review(baseline_ready, bounded)
    assert mixed_review["utility_verdict"] == "MATERIAL_UTILITY"
    assert "TARGET_EXPOSURE" in mixed_review["non_blocking_unknown_dimensions"]
    assert "PERMANENT_LOSS_PATH" in mixed_review["material_treatment_change_dimensions"]


def test_pair_identity_mismatch_and_inconsistent_unknown_are_rejected() -> None:
    baseline = _snapshot("BASELINE")
    informed = _snapshot("CONTEXT")
    informed["company_id"] = "HK:00000"
    with pytest.raises(utility.IndustryUnderwritingUtilityReviewError) as exc:
        _review(baseline, informed)
    assert "treatment_pair.company_id_must_match" in exc.value.findings

    invalid_unknown = _snapshot("UNKNOWN", status="UNKNOWN")
    invalid_unknown["dimensions"]["target_exposure"]["direction"] = "POSITIVE"
    result = utility.validate_treatment_snapshot(invalid_unknown)
    assert not result["valid"]
    assert any("unknown_state_must_not_claim" in finding for finding in result["findings"])


def test_validator_rejects_a_handwritten_positive_verdict() -> None:
    review = _review(_snapshot("BASELINE"), _snapshot("CONTEXT"))
    assert review["utility_verdict"] == "NO_MATERIAL_UTILITY"
    review["utility_verdict"] = "MATERIAL_UTILITY"
    review["investor_conclusion"] = "CONTEXT_CHANGED_MATERIAL_TREATMENT_OR_NARROWED_KEY_RANGE"

    result = utility.validate_industry_underwriting_utility_review(review)

    assert not result["valid"]
    assert "industry_underwriting_utility_review.utility_verdict_not_mechanically_derived" in result["findings"]


def test_json_cli_writes_a_mechanically_valid_review(tmp_path: Path) -> None:
    baseline = _snapshot("BASELINE")
    informed = _snapshot("CONTEXT")
    informed["dimensions"]["permanent_loss_path"]["investment_treatment"].update({
        "base_case_role": "SCENARIO_ONLY",
        "decision_action": "PROCEED_WITH_HAIRCUT",
        "reason": "Context identifies a target-specific irreversible loss path.",
    })
    baseline_path = tmp_path / "baseline.json"
    informed_path = tmp_path / "informed.json"
    output_path = tmp_path / "review.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    informed_path.write_text(json.dumps(informed), encoding="utf-8")

    status = utility.main([
        "--baseline", str(baseline_path),
        "--context-informed", str(informed_path),
        "--review-id", "IUR:CLI:V1",
        "--reviewed-at", REVIEWED_AT,
        "--output", str(output_path),
    ])

    assert status == 0
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["utility_verdict"] == "MATERIAL_UTILITY"
    assert utility.validate_industry_underwriting_utility_review(persisted)["valid"]


def test_schema_declares_closed_review_and_all_five_dimensions() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "industry_underwriting_utility_review_v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["utility_verdict"]["enum"] == [
        "MATERIAL_UTILITY", "NO_MATERIAL_UTILITY",
    ]
    assert set(schema["$defs"]["dimension_id"]["enum"]) == set(utility.DIMENSION_IDS.values())
