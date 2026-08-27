from __future__ import annotations

from copy import deepcopy

from scripts import enterprise_judgment_round10_appliance_v2 as round10


def _source(company_id: str) -> dict:
    code = company_id.split(":", 1)[1]
    return {
        "source_packet_id": f"SOURCE:R10:{code}:FY2017", "company_id": company_id,
        "cutoff_at": round10.CUTOFF_AT, "fact_locators": [f"STATIC:CNINFO:{code}:FY2017:P1"],
        "implemented_action": {"status": "UNKNOWN"}, "outcome_content_read": False,
        "curator_id": f"ROLE:R10:{code}:CURATOR",
        "value_free_outcome_route": {"security_code": code, "organization_id": f"ORG:{code}"},
        "baseline_fields": {
            metric: {
                "source_id": f"CNINFO:{code}:FY2017:{metric}",
                "source_url": f"https://static.cninfo.com.cn/finalpage/2018-04-01/{code}_{metric}.PDF",
                "published_at": "2018-04-01", "field_ref": "PDF p.1", "numeric_value": value,
                "exact_quote": f"{metric} {value}", "statement": "CONSOLIDATED", "scope_note": "listed-consolidated only",
            }
            for metric, value in {"REVENUE": 100.0, "OPERATING_CASH_FLOW": 25.0, "TOTAL_ASSETS": 200.0}.items()
        },
    }


def _package(company_id: str) -> dict:
    return round10.build_company_preoutcome_package(
        company_id=company_id, source_packet=_source(company_id),
    )


def test_round10_epoch_is_scalar_typed_and_one_delta_counts_once() -> None:
    epoch = round10.build_method_epoch()
    result = round10.validate_method_epoch(epoch)
    assert result["valid"], result["findings"]
    assert epoch["treatment_deltas"][0]["method_advantage_count"] == 1
    assert len(epoch["treatment_deltas"]) == 1
    tampered = deepcopy(epoch)
    tampered["treatment_deltas"][0]["method_advantage_count"] = 2
    assert not round10.validate_method_epoch(tampered)["valid"]


def test_round10_freezes_three_distinct_arenas_same_budget_and_v3_contracts() -> None:
    packages = [_package(row["company_id"]) for row in round10.ROSTER]
    batch = round10.build_batch_freeze(packages)
    result = round10.validate_batch_freeze(batch)
    assert result["valid"], result["findings"]
    assert batch["roster_company_ids"] == [row["company_id"] for row in round10.ROSTER]
    assert len({package["company"]["arena_id"] for package in packages}) == 3
    for package in packages:
        assert package["baseline"]["evidence_budget"] == package["enhanced"]["evidence_budget"]
        assert len(package["minimal_field_chains"]) == 3
        for chain in package["minimal_field_chains"]:
            assert chain["measurement_contract"]["schema_version"] == "turtle-minimal-historical-episode-measurement-contract.v2"


def test_round10_unknown_is_local_and_review_cannot_self_accept() -> None:
    batch = round10.build_batch_freeze([_package(row["company_id"]) for row in round10.ROSTER])
    settlements = []
    for package in batch["company_packages"]:
        code = package["company"]["security_code"]
        settlements.append({
            "settlement_id": f"SETTLEMENT:R10:{code}", "company_id": package["company"]["company_id"],
            "cell_results": [
                {"cell_id": f"CELL:R10:{code}:FY2019:REVENUE", "label": "OBSERVED_INCREASE"},
                {"cell_id": f"CELL:R10:{code}:FY2019:OPERATING_CASH_FLOW", "label": "UNKNOWN" if code == "002508" else "OBSERVED_INCREASE"},
                {"cell_id": f"CELL:R10:{code}:FY2019:TOTAL_ASSETS", "label": "MEASUREMENT_MISMATCH"},
            ],
        })
    candidate = round10.build_review_candidate(batch=batch, settlements=settlements)
    assert candidate["automatic_status"] == "INDEPENDENT_REVIEW_REQUIRED"
    assert not candidate["automatic_completion"]
    review = {
        "review_candidate_ref": candidate["review_candidate_id"], "reviewer_id": "ROLE:ROUND10:INDEPENDENT_REVIEWER",
        "review_status": "NO_MATERIAL_UTILITY", "accepted_treatment_delta_ids": [], "utility_basis": None,
        "rights": deepcopy(round10.RIGHTS), "allowed_outputs": ["RESEARCH_AGENDA"],
    }
    result = round10.validate_external_review(review, candidate=candidate)
    assert result["valid"], result["findings"]
    invalid = deepcopy(review)
    invalid["review_status"] = "MATERIAL_UTILITY_CONFIRMED"
    invalid["accepted_treatment_delta_ids"] = ["R10:DELTA:ISSUER_CASH_NOT_OWNER_CASH"]
    invalid["utility_basis"] = "MORE_DIMENSIONS"
    assert not round10.validate_external_review(invalid, candidate=candidate)["valid"]


def test_round10_real_curator_projection_freezes_three_companies_before_outcomes() -> None:
    batch = round10.build_real_preoutcome_batch()
    result = round10.validate_batch_freeze(batch)
    assert result["valid"], result["findings"]
    assert batch["outcome_content_read"] is False
    for package in batch["company_packages"]:
        assert package["source_packet"]["outcome_content_read"] is False
        for chain in package["minimal_field_chains"]:
            assert chain["measurement_contract"]["outcome_acquisition_route"]["annual_report_version_policy"] == "ORIGINAL_ONLY"
            assert chain["prediction"]["method_transfer_rights"] == "NO_METHOD_TRANSFER_RIGHTS"
