from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import enterprise_judgment_real_mechanism_training as mechanism_training
from scripts import enterprise_judgment_round7_multidimensional as round7


ROOT = Path(__file__).resolve().parents[1]
BLOCK_DIR = ROOT / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018"
FROZEN_AT = "2026-08-27T08:30:00+00:00"


def _load(name: str) -> dict:
    return json.loads((BLOCK_DIR / name).read_text(encoding="utf-8"))


def _context() -> dict:
    return {
        "block": _load("04_industry_learning_block.json"),
        "roster_freeze": _load("04_pre_outcome_roster_freeze.json"),
        "consumption_artifacts": [_load(name) for name in round7.CONSUMPTION_FILES],
    }


def _package() -> dict:
    return round7.build_real_preoutcome_package(**_context(), frozen_at=FROZEN_AT)


def test_round7_mechanically_selects_rank3_after_round6_completion() -> None:
    result = round7.derive_round7_target(**_context())
    assert result["valid"], result["findings"]
    selection = result["selection"]
    assert selection["selected_rank"] == 3
    assert selection["transition_id"] == "CCR:600585:20140416:20150415"
    assert selection["company_id"] == "CN:600585"
    assert selection["selection_used_outcome"] is False
    assert selection["selection_used_source_convenience"] is False
    assert "CCR:600801:20160427:20170412" in selection["consumed_transition_ids"]


def test_round6_completion_is_required_to_prevent_reselecting_rank1() -> None:
    context = _context()
    context["consumption_artifacts"] = context["consumption_artifacts"][:-1]
    result = round7.derive_round7_target(**context)
    assert result["valid"], result["findings"]
    assert result["selection"]["selected_rank"] == 1
    assert result["selection"]["company_id"] == "CN:600801"


def test_committed_preoutcome_artifacts_replay_from_builder() -> None:
    artifacts = round7.build_real_preoutcome_artifacts(BLOCK_DIR, frozen_at=FROZEN_AT)
    for name, expected in artifacts.items():
        assert _load(name) == expected
    receipt = artifacts["47_round7_preoutcome_validation_receipt.json"]
    assert receipt["full_enterprise_chain_confirmed"] is True
    assert receipt["outcome_content_read"] is False
    assert receipt["outcome_source_access_state"] == "SEALED_UNTIL_PREOUTCOME_COMMIT"


def test_equal_evidence_budget_and_full_cumulative_chain_are_frozen() -> None:
    package = _package()
    baseline = package["baseline_view"]
    enhanced = package["enhanced_view"]
    budget = package["decision_contract"]["evidence_budget"]
    assert baseline["evidence_budget_id"] == enhanced["evidence_budget_id"] == budget["evidence_budget_id"]
    assert baseline["source_packet_refs"] == enhanced["source_packet_refs"] == budget["source_packet_refs"]
    assert baseline["fact_ids"] == enhanced["fact_ids"]
    assert [cell["dimension"] for cell in enhanced["judgment_cells"]] == round7.JUDGMENT_DIMENSIONS
    assert [cell["dimension"] for cell in baseline["judgment_cells"]] == round7.JUDGMENT_DIMENSIONS
    assert set(enhanced["expected_outcome_cell_ids"]) == {
        cell["cell_id"] for cell in package["outcome_measurement_contract"]["atomic_cells"]
    }


def test_enhanced_chain_separates_external_conditions_action_execution_and_cash() -> None:
    package = _package()
    judgments = {cell["dimension"]: cell for cell in package["enhanced_view"]["judgment_cells"]}
    assert judgments["INITIAL_CONDITIONS"]["causal_credit"] == "NONE"
    assert judgments["IMPLEMENTED_MANAGEMENT_ACTION"]["state"] == "OBSERVED"
    assert judgments["EXECUTION"]["state"] == "MIXED"
    assert judgments["CUSTOMER_COMPETITION_RESPONSE"]["causal_credit"] == "NONE"
    assert judgments["CUSTOMER_COMPETITION_RESPONSE"]["claim_scope"] == "CUSTOMER_AND_COMPETITION_RESPONSE"
    assert "owner-cash" in judgments["WORKING_CAPITAL_CASH_CAPITAL"]["cutoff_assessment"]
    assert judgments["WORKING_CAPITAL_CASH_CAPITAL"]["claim_scope"] == "ISSUER_CASH_CAPITAL_NOT_OWNER_CASH"
    assert "external-and-perimeter" in judgments["STRONGEST_ALTERNATIVE_EXPLANATION"]["cutoff_assessment"]


def test_validator_rejects_missing_dimension_and_outcome_source_leakage() -> None:
    package = _package()
    changed = deepcopy(package)
    changed["enhanced_view"]["judgment_cells"].pop()
    result = round7.validate_preoutcome_package(changed, **_context())
    assert not result["valid"]
    assert "round7_preoutcome.enhanced_view.must_cover_full_cumulative_chain_once_in_order" in result["findings"]

    changed = deepcopy(package)
    changed["selection"]["selection_used_outcome"] = True
    result = round7.validate_preoutcome_package(changed, **_context())
    assert not result["valid"]
    assert "round7_preoutcome.selection_must_be_mechanically_derived" in result["findings"]


def test_measurement_contract_preserves_local_unknown_without_global_failure() -> None:
    contract = _package()["outcome_measurement_contract"]
    validation = mechanism_training.validate_outcome_measurement_contract(contract)
    assert validation["valid"], validation["findings"]
    observations = {
        cell["cell_id"]: {"state": "UNKNOWN"}
        for cell in contract["atomic_cells"]
    }
    one_observed = contract["atomic_cells"][0]["cell_id"]
    observations[one_observed] = {"state": "MATCHED", "baseline": 0.0, "outcome": 0.03}
    settlement = mechanism_training.settle_synthetic_atomic_observations(contract, observations)
    assert settlement["valid"], settlement["findings"]
    results = {row["cell_id"]: row for row in settlement["cell_results"]}
    assert results[one_observed]["label"] == "OBSERVED_INCREASE"
    assert sum(row["label"] == "UNKNOWN" for row in results.values()) == len(results) - 1
    assert all(cell["mismatch_rule"]["propagation"] == "LOCAL_ONLY" for cell in contract["atomic_cells"])


def test_preoutcome_package_grants_no_downstream_rights_or_investment_fields() -> None:
    package = _package()
    assert set(package["rights"].values()) == {"NOT_AUTHORIZED"}
    assert package["contamination_boundary"]["score_authority"] == "NONE"
    serialized = json.dumps(package, ensure_ascii=False).lower()
    for forbidden in ("market_price", "share_price", "buy_band", "portfolio_action"):
        assert forbidden not in serialized


def test_field_records_reuse_existing_acquisition_and_settlement(tmp_path: Path) -> None:
    package = _package()
    contract = package["outcome_measurement_contract"]
    field_records = []
    for cell in contract["atomic_cells"]:
        for raw in cell["raw_input_fields"]:
            field_records.append({
                "cell_id": cell["cell_id"],
                "field_id": raw["field_id"],
                "status": "UNKNOWN",
                "measurement_clock": deepcopy(raw["measurement_clock"]),
                "responsibility_boundary": deepcopy(cell["responsibility_boundary"]),
                "unit": raw["unit"],
                "reason": "SYNTHETIC_RECORD_HAS_NO_OUTCOME_VALUE",
                "sources_considered": [],
            })
    local_pdf = tmp_path / "CN600585_FY2014.pdf"
    local_pdf.write_bytes(b"%PDF-1.4\n")
    artifacts = round7.settle_custodian_field_records(
        package,
        field_records,
        local_pdf_path=local_pdf,
        registry_db=tmp_path / "round7.db",
        registered_at="2026-08-27T08:45:00+00:00",
        observed_at="2026-08-27T08:46:00+00:00",
        settled_at="2026-08-27T08:47:00+00:00",
    )
    assert artifacts["settlement"]["coverage"] == {
        "frozen_cells": len(contract["atomic_cells"]),
        "settled_cells": len(contract["atomic_cells"]),
        "observed_cells": 0,
        "unknown_cells": len(contract["atomic_cells"]),
        "measurement_mismatch_cells": 0,
    }


def test_field_record_adapter_rejects_missing_raw_field_before_settlement(tmp_path: Path) -> None:
    package = _package()
    contract = package["outcome_measurement_contract"]
    field_records = []
    for cell in contract["atomic_cells"]:
        for raw in cell["raw_input_fields"]:
            field_records.append({
                "cell_id": cell["cell_id"],
                "field_id": raw["field_id"],
                "status": "UNKNOWN",
                "measurement_clock": deepcopy(raw["measurement_clock"]),
                "responsibility_boundary": deepcopy(cell["responsibility_boundary"]),
                "unit": raw["unit"],
                "reason": "SYNTHETIC_RECORD_HAS_NO_OUTCOME_VALUE",
                "sources_considered": [],
            })
    local_pdf = tmp_path / "CN600585_FY2014.pdf"
    local_pdf.write_bytes(b"%PDF-1.4\n")
    with pytest.raises(Exception, match="field_records_must_exactly_cover"):
        round7.settle_custodian_field_records(
            package,
            field_records[:-1],
            local_pdf_path=local_pdf,
            registry_db=tmp_path / "round7.db",
            registered_at="2026-08-27T08:45:00+00:00",
            observed_at="2026-08-27T08:46:00+00:00",
            settled_at="2026-08-27T08:47:00+00:00",
        )


def test_committed_real_field_records_replay_canonical_settlement(tmp_path: Path) -> None:
    local_pdf = tmp_path / "CN600585_FY2014.pdf"
    local_pdf.write_bytes(b"%PDF-1.4\n")
    artifacts = round7.settle_custodian_field_records(
        _load("46_round7_multidimensional_preoutcome_package.json"),
        _load("50_round7_custodian_field_records.json"),
        local_pdf_path=local_pdf,
        registry_db=tmp_path / "round7.db",
        registered_at="2026-08-27T08:45:00+00:00",
        observed_at="2026-08-27T08:46:00+00:00",
        settled_at="2026-08-27T08:47:00+00:00",
    )
    assert artifacts["authorization"] == _load("48_round7_outcome_access_authorization.json")
    assert artifacts["settlement"] == _load("51_round7_canonical_field_settlement.json")
    assert artifacts["settlement"]["coverage"] == {
        "frozen_cells": 17,
        "settled_cells": 17,
        "observed_cells": 9,
        "unknown_cells": 7,
        "measurement_mismatch_cells": 1,
    }


def test_real_settlement_keeps_mixed_operating_signals_local() -> None:
    settlement = _load("51_round7_canonical_field_settlement.json")
    results = {row["cell_id"]: row for row in settlement["cell_results"]}
    assert results["CELL:600585:20140416:COMBINED_GROSS_MARGIN"]["status"] == "MEASUREMENT_MISMATCH"
    assert results["CELL:600585:20140416:INVENTORY"]["label"] == "OBSERVED_INCREASE"
    assert results["CELL:600585:20140416:OPERATING_CASH"]["label"] == "OBSERVED_INCREASE"
    assert results["CELL:600585:20140416:DIRECT_CUSTOMER_RESPONSE"]["status"] == "UNKNOWN"
    assert results["CELL:600585:20140416:DIRECT_LOSS_EVENT"]["status"] == "UNKNOWN"


def test_independent_review_and_completion_replay_from_committed_artifacts() -> None:
    package = _load("46_round7_multidimensional_preoutcome_package.json")
    settlement = _load("51_round7_canonical_field_settlement.json")
    review = _load("52_round7_independent_multidimensional_review.json")
    completion = _load("53_round7_completion_receipt.json")

    review_validation = round7.validate_review(review, package=package, settlement=settlement)
    assert review_validation["valid"], review_validation["findings"]
    assert review["reviewer_id"] not in package["roles"].values()
    assert review["overall_verdict"] == "ENHANCED_MATERIALLY_IMPROVED_ENTERPRISE_JUDGMENT"
    assert [row["utility_verdict"] for row in review["dimension_findings"]] == [
        "ENHANCED_BETTER",
        "NO_DIFFERENCE",
        "ENHANCED_BETTER",
        "ENHANCED_BETTER",
        "ENHANCED_BETTER",
        "NO_DIFFERENCE",
        "NOT_DIAGNOSTIC",
        "NO_DIFFERENCE",
    ]

    assert round7.build_real_completion_receipt(package, settlement, review) == completion
    completion_validation = round7.validate_completion(
        completion, package=package, settlement=settlement, review=review,
    )
    assert completion_validation["valid"], completion_validation["findings"]
    assert set(completion["rights"].values()) == {"NOT_AUTHORIZED"}
