from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import enterprise_judgment_episode as episode_module
from scripts import enterprise_judgment_multidimensional_training as multidimensional
from scripts import enterprise_judgment_real_mechanism_training as mechanism_training
from scripts import enterprise_judgment_round8_express as round8
from scripts import enterprise_judgment_source_packet as source_packet


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
