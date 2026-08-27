from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import enterprise_judgment_multidimensional_training as multidimensional
from scripts import enterprise_judgment_real_mechanism_training as mechanism_training
from scripts import enterprise_judgment_round9_appliance as round9
from scripts import judgment_decision_utility as decision_utility


ROOT = Path(
    "docs/development/research/industry_learning_blocks/"
    "CN_APPLIANCE_CHANGHONG_2018_2019_ROUND9"
)


def _read(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_round9_single_company_method_ablation_is_not_forced_into_comparative_topology() -> None:
    block = round9.build_industry_block()
    packets = round9.build_source_packets()
    result = multidimensional.validate_industry_learning_block(
        block, source_packets=packets,
    )
    assert result["valid"], result["findings"]
    assert len(block["members"]) == 1
    selection = round9.build_selection(block, packets)
    assert selection["company_id"] == "CN:600839"
    assert selection["cutoff_at"] == "2018-09-30T23:59:59+08:00"
    assert not selection["selection_used_outcome"]
    assert not selection["selection_used_source_convenience"]


def test_round9_freezes_a_simple_baseline_and_an_eight_dimension_method_on_same_evidence() -> None:
    freeze = round9.build_preoutcome_freeze()
    result = round9.validate_preoutcome_freeze(freeze)
    assert result["valid"], result["findings"]
    package = freeze["canonical_preoutcome_package"]
    baseline = package["baseline_episode"]
    enhanced = package["enhanced_episode"]
    assert len(baseline["question_set"]) == 3
    assert len([claim for claim in baseline["claims"] if claim["cell_status"] != "NOT_APPLICABLE"]) == 3
    assert len(enhanced["claims"]) == 8
    assert {claim["judgment_dimension"] for claim in enhanced["claims"]} == set(
        decision_utility.DIMENSIONS
    )
    baseline_locators = {
        locator
        for claim in baseline["claims"]
        for locator in claim["evidence_locator_refs"]
    }
    enhanced_locators = {
        locator
        for claim in enhanced["claims"]
        for locator in claim["evidence_locator_refs"]
    }
    assert baseline_locators == enhanced_locators == set(round9.LOCATOR.values())
    pairing = package["decision_utility_pairing"]
    assert pairing["baseline_research_cost_hours"] == pairing["enhanced_research_cost_hours"]


def test_round9_measurement_contract_has_strict_post_cutoff_clocks_and_typed_boundaries() -> None:
    contract = round9.build_measurement_contract()
    result = mechanism_training.validate_outcome_measurement_contract(contract)
    assert result["valid"], result["findings"]
    assert len(contract["atomic_cells"]) == 11
    assert contract["outcome_window"]["period_start"] == "2019-01-01T00:00:00+08:00"
    assert {
        cell["responsibility_boundary"]["responsibility_unit_id"]
        for cell in contract["atomic_cells"]
    } == {
        "INDUSTRY_CONTEXT:CN:WHITE_GOODS",
        "ISSUER_CONSOLIDATED:CN:600839",
        "PRODUCT_ARENA:CN:600839:WHITE_GOODS",
        "ORDINARY_SHARE_CASH:CN:600839",
    }
    for cell in contract["atomic_cells"]:
        clock = cell["measurement_clock"]
        if clock["clock_kind"] == "FLOW_PERIOD":
            assert clock["flow_period"]["period_start"] == "2019-01-01"
            assert clock["flow_period"]["period_end"] == "2019-12-31"
        elif clock["clock_kind"] == "EVENT_WINDOW":
            assert clock["event_window"]["event_start"] == "2019-01-01"
            assert clock["event_window"]["event_end"] == "2019-12-31"
        else:
            assert clock["clock_kind"] == "BALANCE_AS_OF"
            assert clock["balance_as_of"]["as_of"] == "2019-12-31"


def test_round9_source_identity_remains_unresolved_until_after_freeze_commit() -> None:
    freeze = round9.build_preoutcome_freeze()
    source = freeze["canonical_preoutcome_package"]["outcome_measurement_contract"]["source_access"]
    assert source["source_id"] == round9.UNRESOLVED_SOURCE_ID
    assert source["official_url"] == round9.UNRESOLVED_SOURCE_URL
    assert source["source_available_at"] is None
    assert source["source_available_date"] is None
    assert not freeze["outcome_source_located"]
    assert not freeze["outcome_content_read"]
    policy = freeze["source_resolution_policy"]
    assert policy["resolution_timing"] == "ONLY_AFTER_PREOUTCOME_FREEZE_COMMIT"
    assert policy["permitted_metadata_use"] == "ENUMERATE_AND_BIND_STATIC_PDF_IDENTITY_ONLY"


def test_round9_method_specific_resolution_rules_are_frozen_and_tamper_evident() -> None:
    freeze = round9.build_preoutcome_freeze()
    resolution = freeze["method_resolution_contract"]
    assert resolution["baseline"]["method_kind"] == (
        "SIMPLE_PRODUCT_TREND_WITH_GROUP_BOUNDARY_GUARD"
    )
    assert resolution["enhanced"]["method_kind"] == "EIGHT_DIMENSION_NO_SCORE_QUESTION_SKELETON"
    assert len(resolution["baseline"]["input_cell_ids"]) == 5
    assert len(resolution["enhanced"]["dimension_rules"]) == 8
    assert resolution["paired_utility_rules"]["method_release"] == (
        "CANDIDATE_ONLY_REGARDLESS_OF_ONE_SAMPLE_RESULT"
    )
    tampered = deepcopy(freeze)
    tampered["method_resolution_contract"]["enhanced"]["dimension_rules"][2][
        "resolution_rule"
    ] = "Credit execution whenever group revenue rises."
    result = round9.validate_preoutcome_freeze(tampered)
    assert not result["valid"]
    assert "round9_preoutcome_freeze_must_equal_deterministic_builder" in result["findings"]


def _fully_observed_labels() -> dict[str, str]:
    labels = {
        cell_id: "OBSERVED_STABLE"
        for cell_id in round9.CELL.values()
    }
    for name in (
        "INDUSTRY_CONTEXT_EVENT", "WHITE_GOODS_ACTION_EVENT",
        "PORTFOLIO_SCOPE_EVENT", "OWNER_CASH_BRIDGE_EVENT",
    ):
        labels[round9.CELL[name]] = "OBSERVED_NO"
    return labels


def _synthetic_settlement(labels: dict[str, str]) -> dict:
    rows = []
    for cell_id in round9.CELL.values():
        label = labels[cell_id]
        status = (
            "UNKNOWN" if label == "UNKNOWN"
            else "MEASUREMENT_MISMATCH" if label == "MEASUREMENT_MISMATCH"
            else "OBSERVED"
        )
        rows.append({
            "cell_id": cell_id,
            "status": status,
            "label": label,
            "computed_value": None if status != "OBSERVED" else 0.0,
            "mismatch_propagation": "LOCAL_ONLY",
        })
    return {
        "settlement_id": "SYNTHETIC:SETTLEMENT:R9",
        "company_id": round9.COMPANY_ID,
        "cutoff_at": round9.CUTOFF_AT,
        "measurement_contract_ref": {
            "measurement_contract_id": round9.MEASUREMENT_CONTRACT_ID,
            "measurement_contract_version": 3,
        },
        "cell_results": rows,
    }


def test_round9_resolver_does_not_call_scope_discovery_an_avoided_error() -> None:
    labels = _fully_observed_labels()
    labels[round9.CELL["PORTFOLIO_SCOPE_EVENT"]] = "OBSERVED_YES"
    resolved = round9.resolve_method_outputs(labels)
    assert resolved["baseline"]["white_goods_direction"] == "WHITE_GOODS_UNKNOWN"
    assert "AVOIDED_ERROR" not in set(resolved["paired_utility"].values())
    assert "MATERIAL_IMPROVEMENT" not in set(resolved["paired_utility"].values())


def test_round9_resolver_does_not_call_same_direction_plus_scope_an_avoided_error() -> None:
    labels = _fully_observed_labels()
    for name in (
        "GROUP_REVENUE_LEVEL", "WHITE_GOODS_REVENUE_LEVEL",
        "WHITE_GOODS_GROSS_MARGIN", "GROUP_OCF_LEVEL",
    ):
        labels[round9.CELL[name]] = "OBSERVED_INCREASE"
    labels[round9.CELL["WHITE_GOODS_ACTION_EVENT"]] = "OBSERVED_YES"
    labels[round9.CELL["PORTFOLIO_SCOPE_EVENT"]] = "OBSERVED_YES"
    resolved = round9.resolve_method_outputs(labels)
    assert resolved["baseline"]["white_goods_direction"] == "WHITE_GOODS_POSITIVE"
    assert resolved["enhanced"]["dimension_outputs"]["EXECUTION"] == "SUPPORTED_TREND"
    assert resolved["paired_utility"]["EXECUTION"] == "NO_DIFFERENCE"
    assert "AVOIDED_ERROR" not in set(resolved["paired_utility"].values())
    assert resolved["common_decision_treatments"] == {
        "baseline_operating": "CONTINUE_OPERATING_UNDERWRITING",
        "enhanced_operating": "RESEARCH_REQUIRED",
        "baseline_owner_cash": "OWNER_CASH_UNKNOWN",
        "enhanced_owner_cash": "OWNER_CASH_UNKNOWN",
    }
    assert resolved["paired_utility"]["ADAPTATION_PERMANENT_LOSS"] == "MATERIAL_IMPROVEMENT"
    assert resolved["paired_utility"]["STRONGEST_ALTERNATIVE_EXPLANATION"] == "MATERIAL_IMPROVEMENT"


def test_round9_resolver_preserves_unavailable_inputs_as_not_diagnostic() -> None:
    labels = _fully_observed_labels()
    labels[round9.CELL["WHITE_GOODS_GROSS_MARGIN"]] = "MEASUREMENT_MISMATCH"
    resolved = round9.resolve_method_outputs(labels)
    assert resolved["baseline"]["white_goods_direction"] == "NOT_DIAGNOSTIC"
    assert resolved["enhanced"]["dimension_outputs"]["EXECUTION"] == "NOT_DIAGNOSTIC"
    assert resolved["paired_utility"]["EXECUTION"] == "NOT_DIAGNOSTIC"
    assert "AVOIDED_ERROR" not in set(resolved["paired_utility"].values())


def test_round9_resolver_abstains_when_group_and_product_directions_reverse() -> None:
    labels = _fully_observed_labels()
    labels[round9.CELL["GROUP_REVENUE_LEVEL"]] = "OBSERVED_INCREASE"
    labels[round9.CELL["WHITE_GOODS_REVENUE_LEVEL"]] = "OBSERVED_DECREASE"
    labels[round9.CELL["WHITE_GOODS_GROSS_MARGIN"]] = "OBSERVED_DECREASE"
    labels[round9.CELL["WHITE_GOODS_ACTION_EVENT"]] = "OBSERVED_YES"
    resolved = round9.resolve_method_outputs(labels)
    assert resolved["baseline"]["group_product_boundary_guard"] == "DIVERGENT"
    assert resolved["baseline"]["white_goods_direction"] == "WHITE_GOODS_UNKNOWN"
    assert resolved["enhanced"]["dimension_outputs"]["EXECUTION"] == "WEAKENED_TREND"
    assert resolved["paired_utility"]["EXECUTION"] == "NOT_DIAGNOSTIC"


def test_round9_forged_resolution_receipt_is_rejected() -> None:
    labels = _fully_observed_labels()
    settlement = _synthetic_settlement(labels)
    receipt = round9.build_method_resolution_receipt(
        settlement,
        resolved_at="2020-05-01T00:00:00+08:00",
    )
    result = round9.validate_method_resolution_receipt(
        receipt, canonical_settlement=settlement,
    )
    assert result["valid"], result["findings"]
    forged = deepcopy(receipt)
    forged["resolved_outputs"]["paired_utility"]["EXECUTION"] = "AVOIDED_ERROR"
    result = round9.validate_method_resolution_receipt(
        forged, canonical_settlement=settlement,
    )
    assert not result["valid"]
    assert "method_resolution_receipt_does_not_replay_frozen_resolver" in result["findings"]


def test_round9_resolution_receipt_rejects_self_consistent_labels_not_in_settlement() -> None:
    labels = _fully_observed_labels()
    settlement = _synthetic_settlement(labels)
    altered_labels = deepcopy(labels)
    altered_labels[round9.CELL["GROUP_REVENUE_LEVEL"]] = "OBSERVED_INCREASE"
    altered_settlement = _synthetic_settlement(altered_labels)
    forged = round9.build_method_resolution_receipt(
        altered_settlement,
        resolved_at="2020-05-01T00:00:00+08:00",
    )
    result = round9.validate_method_resolution_receipt(
        forged, canonical_settlement=settlement,
    )
    assert not result["valid"]
    assert "method_resolution_receipt_does_not_replay_frozen_resolver" in result["findings"]


def test_round9_resolution_receipt_rejects_wrong_ref_and_duplicate_cells() -> None:
    labels = _fully_observed_labels()
    settlement = _synthetic_settlement(labels)
    receipt = round9.build_method_resolution_receipt(
        settlement,
        resolved_at="2020-05-01T00:00:00+08:00",
    )
    wrong_ref = deepcopy(settlement)
    wrong_ref["settlement_id"] = "SYNTHETIC:OTHER"
    result = round9.validate_method_resolution_receipt(
        receipt, canonical_settlement=wrong_ref,
    )
    assert not result["valid"]
    duplicated = deepcopy(settlement)
    duplicated["cell_results"][-1] = deepcopy(duplicated["cell_results"][0])
    result = round9.validate_method_resolution_receipt(
        receipt, canonical_settlement=duplicated,
    )
    assert not result["valid"]
    assert "complete, unique and ordered" in result["findings"][0]


def test_round9_checked_in_preoutcome_artifacts_replay_from_builders() -> None:
    freeze = _read("07_round9_preoutcome_freeze.json")
    assert freeze == round9.build_preoutcome_freeze()
    assert _read("01_industry_learning_block.json") == freeze["industry_block"]
    assert _read("02_source_packet_receipts.json") == freeze["source_packets"]
    assert _read("03_mechanical_selection_receipt.json") == freeze[
        "mechanical_selection_receipt"
    ]
    assert _read("04_canonical_preoutcome_package.json") == freeze[
        "canonical_preoutcome_package"
    ]
    assert _read("05_source_resolution_policy.json") == freeze["source_resolution_policy"]
    assert _read("06_method_resolution_contract.json") == freeze[
        "method_resolution_contract"
    ]


def test_round9_canonical_package_rejects_a_posthoc_evidence_budget_change() -> None:
    freeze = round9.build_preoutcome_freeze()
    package = deepcopy(freeze["canonical_preoutcome_package"])
    package["baseline_episode"]["claims"][2]["evidence_locator_refs"] = [
        round9.LOCATOR["CASH"]
    ]
    result = multidimensional.validate_preoutcome_package(
        package,
        block=freeze["industry_block"],
        source_packets=freeze["source_packets"],
        selection=freeze["mechanical_selection_receipt"],
    )
    assert not result["valid"]
    assert any("same_frozen_evidence_locator_set" in finding for finding in result["findings"])
