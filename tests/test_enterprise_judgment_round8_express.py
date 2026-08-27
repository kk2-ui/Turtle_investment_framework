from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import enterprise_judgment_episode as episode_module
from scripts import enterprise_judgment_multidimensional_training as multidimensional
from scripts import enterprise_judgment_real_mechanism_training as mechanism_training
from scripts import enterprise_judgment_round8_express as round8
from scripts import enterprise_judgment_source_packet as source_packet
from scripts import judgment_decision_utility as decision_utility
from scripts import outcome_measurement_acquisition as measurement_acquisition


ROOT = Path("docs/development/research/industry_learning_blocks/CN_FRANCHISE_EXPRESS_2018_2019")


def _read(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _objects() -> tuple[dict, list[dict], dict, dict]:
    return (
        _read("01_industry_learning_block.json"),
        _read("02_source_packet_receipts.json"),
        _read("03_selection_receipt.json"),
        _read("04_preoutcome_package.json"),
    )


def test_round8_block_mechanically_selects_yunda_without_outcome_or_source_convenience() -> None:
    block, packets, selection, _ = _objects()
    result = multidimensional.validate_industry_learning_block(block, source_packets=packets)
    assert result["valid"], result["findings"]
    assert len(block["members"]) == 3
    assert block["observation_window"]["event_start"] == "2019-05-02"
    derived = multidimensional.derive_selection(block, source_packets=packets)
    assert derived["valid"], derived["findings"]
    assert derived["selection"] == selection
    assert selection["company_id"] == "CN:002120"
    assert not selection["selection_used_outcome"]
    assert not selection["selection_used_source_convenience"]


def test_round8_preoutcome_package_is_complete_same_evidence_and_outcome_sealed() -> None:
    block, packets, selection, package = _objects()
    result = multidimensional.validate_preoutcome_package(
        package, block=block, source_packets=packets, selection=selection,
    )
    assert result["valid"], result["findings"]
    baseline = package["baseline_episode"]
    enhanced = package["enhanced_episode"]
    for episode in (baseline, enhanced):
        assert len(episode["claims"]) == 8
        assert {claim["judgment_dimension"] for claim in episode["claims"]} == set(round8.DIMENSIONS)
        assert all(cell["status"] == "UNKNOWN" for cell in episode["outcome_cells"])
        assert all(cell["custodian_receipt_ref"] == "" for cell in episode["outcome_cells"])
    baseline_locators = {
        locator for claim in baseline["claims"] for locator in claim["evidence_locator_refs"]
    }
    enhanced_locators = {
        locator for claim in enhanced["claims"] for locator in claim["evidence_locator_refs"]
    }
    assert baseline_locators == enhanced_locators
    assert package["outcome_measurement_contract"]["source_access"]["access_state"] == "SEALED_UNTIL_PREOUTCOME_COMMIT"


def test_round8_claims_are_bound_to_declared_packet_fields_and_locators() -> None:
    block, packets, selection, package = _objects()
    selected_packet = packets[0]
    packet_result = source_packet.validate_source_packet_receipt(selected_packet)
    assert packet_result["valid"], packet_result["findings"]
    locator_ids = list(packet_result["locator_map"])
    for episode in (package["baseline_episode"], package["enhanced_episode"]):
        result = episode_module.validate_episode_manifest(
            episode,
            decision_contract=package["decision_contract"],
            evidence_locator_ids=locator_ids,
        )
        assert result["valid"], result["findings"]

    tampered = deepcopy(package)
    tampered["baseline_episode"]["claims"][0]["evidence_locator_refs"] = [
        "LOC:002120:FY2018:CASH_CAPITAL"
    ]
    result = multidimensional.validate_preoutcome_package(
        tampered, block=block, source_packets=packets, selection=selection,
    )
    assert not result["valid"]
    assert any("locator_not_materially_bound_to_claim" in finding for finding in result["findings"])


def test_round8_measurement_contract_separates_strict_events_from_mixed_fy2019_flows() -> None:
    _, _, _, package = _objects()
    contract = package["outcome_measurement_contract"]
    result = mechanism_training.validate_outcome_measurement_contract(contract)
    assert result["valid"], result["findings"]
    assert len(contract["atomic_cells"]) == 15
    event_cells = [
        cell for cell in contract["atomic_cells"]
        if cell["measurement_clock"]["clock_kind"] == "EVENT_WINDOW"
    ]
    flow_cells = [
        cell for cell in contract["atomic_cells"]
        if cell["measurement_clock"]["clock_kind"] == "FLOW_PERIOD"
    ]
    assert event_cells
    assert all(
        cell["measurement_clock"]["event_window"]["event_start"] == "2019-05-02"
        for cell in event_cells
    )
    assert flow_cells
    assert all(
        cell["outcome_period"]["fiscal_period"] == "FY2019_MIXED_CLOCK_CONTEXT"
        for cell in flow_cells
    )
    assert any("MIXED_CLOCK_CONTEXT" in cell["responsibility_boundary"]["scope_requirement"] for cell in flow_cells)


def test_round8_builder_reproduces_checked_in_preoutcome_artifact() -> None:
    block, packets, selection, package = _objects()
    assert round8.build_preoutcome_package(block, packets, selection) == package


def test_round8_custodian_records_preserve_local_unknown_and_scope_mismatch() -> None:
    _, _, _, package = _objects()
    records = round8.build_custodian_field_records(package)
    assert records == _read("07_custodian_field_records.json")
    contract = package["outcome_measurement_contract"]
    expected = [
        (cell["cell_id"], raw["field_id"])
        for cell in contract["atomic_cells"]
        for raw in cell["raw_input_fields"]
    ]
    assert [(record["cell_id"], record["field_id"]) for record in records] == expected
    by_field = {record["field_id"]: record for record in records}
    assert by_field["FIELD:002120:FY2019:OPERATING_CASH_FLOW"]["raw_value"] == 5_035_636_370.68
    assert by_field["FIELD:002120:FY2019:NETWORK_SCALE_EVENT"]["status"] == "UNKNOWN"
    assert by_field["FIELD:002120:FY2019:EXPRESS_REVENUE_RPP_NUMERATOR"]["status"] == "MEASUREMENT_MISMATCH"
    assert "DISPATCH_FEES" in by_field["FIELD:002120:FY2019:EXPRESS_REVENUE_RPP_NUMERATOR"]["reason"]
    assert by_field["FIELD:002120:FY2019:EFFECTIVE_COMPLAINT_RATE"]["status"] == "MEASUREMENT_MISMATCH"
    assert "PER_MILLION" in by_field["FIELD:002120:FY2019:EFFECTIVE_COMPLAINT_RATE"]["reason"]


def test_round8_real_pdf_settlement_keeps_usable_cells_moving(tmp_path: Path) -> None:
    pdf = Path("/tmp/CN002120_FY2019_1207682788.pdf")
    if not pdf.exists():
        pytest.skip("authorized local FY2019 CNINFO PDF is not present")
    _, _, _, package = _objects()
    records = round8.build_custodian_field_records(package)
    page_receipts = round8.build_page_extraction_receipts(records)
    assert page_receipts == _read("07a_page_extraction_receipts.json")
    registry_db = tmp_path / "round8.sqlite3"
    artifacts = round8.settle_custodian_field_records(
        package,
        records,
        page_extraction_receipts=page_receipts,
        local_pdf_path=pdf,
        registry_db=registry_db,
        registered_at="2020-05-01T00:00:00+08:00",
        observed_at="2020-05-01T00:01:00+08:00",
        settled_at="2020-05-01T00:02:00+08:00",
    )
    settlement = artifacts["settlement"]
    assert settlement == _read("08_outcome_settlement.json")
    assert settlement["coverage"] == {
        "frozen_cells": 15,
        "settled_cells": 15,
        "observed_cells": 6,
        "unknown_cells": 3,
        "measurement_mismatch_cells": 6,
    }
    by_cell = {row["cell_id"]: row for row in settlement["cell_results"]}
    assert by_cell[round8.CELL["INDUSTRY_PARCEL_GROWTH"]]["status"] == "MEASUREMENT_MISMATCH"
    assert by_cell[round8.CELL["ISSUER_MINUS_INDUSTRY_GROWTH_SPREAD"]]["status"] == "MEASUREMENT_MISMATCH"
    assert by_cell[round8.CELL["MARKET_SHARE_CHANGE"]]["computed_value"] == pytest.approx(0.0202)
    assert by_cell[round8.CELL["COMPLAINT_RATE_CHANGE"]]["status"] == "MEASUREMENT_MISMATCH"
    assert by_cell[round8.CELL["OPERATING_CASH_FLOW"]]["computed_value"] == pytest.approx(0.355681551)
    assert by_cell[round8.CELL["EXPRESS_REVENUE_PER_PARCEL"]]["status"] == "MEASUREMENT_MISMATCH"
    assert by_cell[round8.CELL["NETWORK_SCALE_EVENT"]]["status"] == "UNKNOWN"
    acquisition = measurement_acquisition.validate_acquisition_result(
        artifacts["acquisition_result"],
        measurement_contract=package["outcome_measurement_contract"],
        outcome_access_authorization=artifacts["authorization"],
    )
    assert acquisition["valid"], acquisition["findings"]
    adjudication = round8.build_scope_clock_adjudication(
        package, settlement, adjudicated_at="2020-05-01T00:02:30+08:00",
    )
    assert adjudication == _read("09_scope_clock_adjudication.json")
    assert all(row["causal_credit"] == "NONE" for row in adjudication["cells"])
    evaluation = round8.build_utility_evaluation(
        package,
        settlement,
        adjudication,
        reviewer_id="ROLE:ROUND8:INDEPENDENT_UTILITY_REVIEWER",
        evaluated_at="2020-05-01T00:03:00+08:00",
        registry_db=registry_db,
    )
    utility = decision_utility.validate_decision_utility_evaluation(
        evaluation,
        pairing=package["decision_utility_pairing"],
        contract=package["decision_contract"],
        baseline_episode=package["baseline_episode"],
        enhanced_episode=package["enhanced_episode"],
    )
    assert utility["valid"], utility["findings"]
    assert utility["learning_authorization"] == "CANDIDATE_ONLY"
    assessments = {
        finding["dimension_id"]: finding["enhanced_assessment"]
        for finding in evaluation["dimension_findings"]
    }
    assert assessments == {
        "INITIAL_CONDITIONS": "NOT_DIAGNOSTIC",
        "IMPLEMENTED_MANAGEMENT_ACTION": "NO_DIFFERENCE",
        "EXECUTION": "NOT_DIAGNOSTIC",
        "CUSTOMER_COMPETITION_RESPONSE": "NO_DIFFERENCE",
        "UNIT_ECONOMICS": "NOT_DIAGNOSTIC",
        "WORKING_CAPITAL_CASH_CAPITAL": "NO_DIFFERENCE",
        "ADAPTATION_PERMANENT_LOSS": "NO_DIFFERENCE",
        "STRONGEST_ALTERNATIVE_EXPLANATION": "NO_DIFFERENCE",
    }
    tampered_settlement = deepcopy(settlement)
    tampered_settlement["cell_results"][3]["status"] = "MEASUREMENT_MISMATCH"
    with pytest.raises(ValueError, match="canonical replay"):
        round8.build_utility_evaluation(
            package,
            tampered_settlement,
            adjudication,
            reviewer_id="ROLE:ROUND8:INDEPENDENT_UTILITY_REVIEWER",
            evaluated_at="2020-05-01T00:03:00+08:00",
            registry_db=registry_db,
        )
    tampered_adjudication = round8.build_scope_clock_adjudication(
        package,
        tampered_settlement,
        adjudicated_at=adjudication["adjudicated_at"],
    )
    with pytest.raises(ValueError, match="canonical replay"):
        round8.build_utility_evaluation(
            package,
            tampered_settlement,
            tampered_adjudication,
            reviewer_id="ROLE:ROUND8:INDEPENDENT_UTILITY_REVIEWER",
            evaluated_at="2020-05-01T00:03:00+08:00",
            registry_db=registry_db,
        )
    acceptance = _read("11a_independent_utility_review_acceptance.json")
    completion = round8.build_completion_receipt(
        package,
        settlement,
        adjudication,
        evaluation,
        acceptance,
        registry_db=registry_db,
    )
    assert completion["method_conclusion"] == round8.METHOD_CONCLUSION
    assert all(value == "NOT_AUTHORIZED" for value in completion["rights"].values())
    checked_evaluation = _read("11_decision_utility_evaluation.json")
    reproduced_evaluation = round8.build_utility_evaluation(
        package,
        settlement,
        adjudication,
        reviewer_id=checked_evaluation["reviewer_id"],
        evaluated_at=checked_evaluation["evaluated_at"],
        registry_db=registry_db,
    )
    assert reproduced_evaluation == checked_evaluation
    assert round8.build_completion_receipt(
        package,
        settlement,
        adjudication,
        reproduced_evaluation,
        acceptance,
        registry_db=registry_db,
    ) == _read("12_round8_completion_receipt.json")

    tampered_records = deepcopy(records)
    observed_index = next(
        index for index, record in enumerate(tampered_records) if record["status"] == "OBSERVED"
    )
    tampered_records[observed_index]["raw_value"] += 0.01
    with pytest.raises(ValueError, match="raw_value_not_derived_from_pdf_page"):
        round8.settle_custodian_field_records(
            package,
            tampered_records,
            page_extraction_receipts=page_receipts,
            local_pdf_path=pdf,
            registry_db=tmp_path / "tampered-value.sqlite3",
            registered_at="2020-05-01T00:00:00+08:00",
            observed_at="2020-05-01T00:01:00+08:00",
            settled_at="2020-05-01T00:02:00+08:00",
        )
    tampered_unit = deepcopy(records)
    tampered_unit[observed_index]["unit"] = "COUNT"
    with pytest.raises(ValueError, match="unit_must_match_frozen_field"):
        round8.settle_custodian_field_records(
            package,
            tampered_unit,
            page_extraction_receipts=page_receipts,
            local_pdf_path=pdf,
            registry_db=tmp_path / "tampered-unit.sqlite3",
            registered_at="2020-05-01T00:00:00+08:00",
            observed_at="2020-05-01T00:01:00+08:00",
            settled_at="2020-05-01T00:02:00+08:00",
        )
    missing_acceptance = deepcopy(acceptance)
    missing_acceptance["accepted_dimension_conclusions"].pop("EXECUTION")
    with pytest.raises(ValueError, match="dimension_conclusions_mismatch"):
        round8.build_completion_receipt(
            package,
            settlement,
            adjudication,
            evaluation,
            missing_acceptance,
            registry_db=registry_db,
        )
    unrelated_evaluation = deepcopy(evaluation)
    unrelated_evaluation["dimension_findings"][0]["rationale"] = "Unrelated post-outcome interpretation."
    with pytest.raises(ValueError, match="evaluation does not replay"):
        round8.build_completion_receipt(
            package,
            settlement,
            adjudication,
            unrelated_evaluation,
            acceptance,
            registry_db=registry_db,
        )
    with pytest.raises(ValueError, match="independent utility acceptance invalid"):
        round8.build_completion_receipt(
            package,
            settlement,
            adjudication,
            evaluation,
            None,
            registry_db=registry_db,
        )
    reviewer_drift = deepcopy(acceptance)
    reviewer_drift["reviewer_id"] = "ROLE:ROUND8:OTHER_REVIEWER"
    with pytest.raises(ValueError, match="reviewer_mismatch"):
        round8.build_completion_receipt(
            package,
            settlement,
            adjudication,
            evaluation,
            reviewer_drift,
            registry_db=registry_db,
        )
