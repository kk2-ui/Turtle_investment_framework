from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import judgment_historical_training as history
from scripts import judgment_pit_forecast as pit
from tests.test_judgment_selection_discovery import _stage0_static_package


H1_REF = {"receipt_id": "H1:SYNTHETIC:FORECAST:V1", "receipt_version": 1}
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _universe_and_h1() -> tuple[dict, dict]:
    h1 = _stage0_static_package()
    projection = history.project_stage0_h1_to_universe_and_carrier_seed(h1, h1_receipt_ref=H1_REF)
    assert projection["valid"], projection["findings"]
    return projection["universe_snapshot"], h1


def _source(h1: dict, issuer_id: str) -> dict:
    return next(source for source in h1["static_pdf_sources"] if source["issuer_id"] == issuer_id)


def _probabilities(dimension_id: str) -> list[dict]:
    labels = pit.RISK_LABELS if dimension_id == "PERMANENT_LOSS_RISK" else pit.NON_RISK_LABELS
    return [
        {"label": labels[0], "probability": 0.30},
        {"label": labels[1], "probability": 0.40},
        {"label": labels[2], "probability": 0.30},
    ]


def _forecast(
    universe: dict, h1: dict, company_id: str, *, forecast_id: str | None = None,
    decision_contract_ref: dict | None = None,
) -> dict:
    member = next(value for value in universe["members"] if value["company_id"] == company_id)
    source = _source(h1, member["issuer_id"])
    reference = {
        "source_id": source["source_id"],
        "published_at": source["published_at"],
        "field_ref": source["field_refs"][0],
    }
    forecast = {
        "schema_version": pit.FORECAST_SCHEMA_VERSION_V2 if decision_contract_ref else pit.FORECAST_SCHEMA_VERSION,
        "forecast_id": forecast_id or f"FORECAST:SYNTHETIC:{company_id}",
        "forecast_epoch_id": pit.FORECAST_EPOCH_ID_V2 if decision_contract_ref else pit.FORECAST_EPOCH_ID,
        "company_id": company_id,
        "issuer_id": member["issuer_id"],
        "subject_id": member["subject_id"],
        "cutoff_at": universe["cutoff_at"],
        "forecast_windows": list(pit.FORECAST_WINDOWS),
        "source_packet_refs": [H1_REF],
        "model_memory_mitigation": {
            "mode": "MODEL_MEMORY_MITIGATED",
            "isolated_forecaster_id": "SYNTHETIC:ISOLATED:FORECASTER",
            "known_outcome_access": "NONE",
            "price_access": "NONE",
            "post_cutoff_access": "NONE",
            "network_route": "H1_DECLARED_STATIC_PDF_ONLY",
            "notes": "Synthetic fixture keeps the forecast agent away from outcomes and price.",
        },
        "dimensions": [
            {
                "dimension_id": dimension_id,
                "evidence_status": "MODEL_UNCERTAIN",
                "evidence_refs": [reference],
                "forecast_by_window": [
                    {
                        "window_id": window_id,
                        "baseline_reference": "Cutoff risk-set baseline, not a later realised outcome.",
                        "probabilities": _probabilities(dimension_id),
                    }
                    for window_id in pit.FORECAST_WINDOWS
                ],
                "rationale": "A cutoff-visible source supports a probability forecast, not a causal action conclusion.",
            }
            for dimension_id in pit.FORECAST_DIMENSIONS
        ],
        "object_class": "PIT_COMPANY_STATE_FORECAST",
        "claim_class": "PROSPECTIVE_STATE_TRAJECTORY",
        "allowed_outputs": ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }
    if decision_contract_ref:
        forecast["decision_contract_ref"] = deepcopy(decision_contract_ref)
    return forecast


def test_company_state_forecast_requires_h1_state_probability_or_explicit_coverage_gap() -> None:
    universe, h1 = _universe_and_h1()
    forecast = _forecast(universe, h1, universe["members"][0]["company_id"])
    result = pit.validate_company_state_forecast(forecast, universe_snapshot=universe, stage0_package=h1)
    assert result["valid"], result["findings"]

    ineligible = deepcopy(forecast)
    ineligible["dimensions"][0]["evidence_status"] = "EVIDENCE_INELIGIBLE"
    ineligible["dimensions"][0]["forecast_by_window"] = [{
        "window_id": "ONE_YEAR", "baseline_reference": "forged", "probabilities": _probabilities("NORMAL_EARNINGS"),
    }]
    rejected = pit.validate_company_state_forecast(ineligible, universe_snapshot=universe, stage0_package=h1)
    assert not rejected["valid"]
    assert "forecast.dimensions[0].ineligible_dimension_cannot_emit_prediction" in rejected["findings"]

    wrong_issuer_source = deepcopy(forecast)
    other_member = universe["members"][1]
    other_source = _source(h1, other_member["issuer_id"])
    wrong_issuer_source["dimensions"][0]["evidence_refs"][0].update({
        "source_id": other_source["source_id"], "published_at": other_source["published_at"],
    })
    rejected = pit.validate_company_state_forecast(wrong_issuer_source, universe_snapshot=universe, stage0_package=h1)
    assert not rejected["valid"]
    assert "forecast.dimensions[0].evidence_refs[0].source_issuer_must_match_forecast_company" in rejected["findings"]

    wrong_page = deepcopy(forecast)
    wrong_page["dimensions"][0]["evidence_refs"][0]["field_ref"] = "Synthetic official annual report PDF p999."
    rejected = pit.validate_company_state_forecast(wrong_page, universe_snapshot=universe, stage0_package=h1)
    assert not rejected["valid"]
    assert "forecast.dimensions[0].evidence_refs[0].field_ref_must_match_h1_declared_pdf_page" in rejected["findings"]

    mismatched_h1 = deepcopy(h1)
    mismatched_h1["selection_as_of"] = "2020-07-01T00:00:00+08:00"
    rejected = pit.validate_company_state_forecast(forecast, universe_snapshot=universe, stage0_package=mismatched_h1)
    assert not rejected["valid"]
    assert "forecast.cutoff_at_must_match_h1_static_receipt" in rejected["findings"]


def test_v3_measurement_contract_maps_each_observed_cell_without_reading_forecast_rationale() -> None:
    universe, h1 = _universe_and_h1()
    v2 = _forecast(
        universe, h1, universe["members"][0]["company_id"],
        decision_contract_ref={"contract_id": "DC:SYNTHETIC:FORECAST:V1", "contract_version": 1},
    )
    from tests.test_judgment_training_decision_contract import _contract
    decision_contract = _contract(v2)
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    assert pit.validate_forecast_outcome_measurement_contract(measurement_contract)["valid"]
    v3 = _v3_forecast(v2, measurement_contract)
    assert pit.validate_company_state_forecast(v3, universe_snapshot=universe, stage0_package=h1)["valid"]
    settlement = _v3_observed_settlement(v3, measurement_contract)
    observations = _v3_observation_receipts(v3, measurement_contract)
    result = pit.settle_company_state_forecast(
        v3, settlement, measurement_contract=measurement_contract, observation_receipts=observations,
    )
    assert result["valid"] and result["coverage"]["observed_scored_cells"] == 18

    ratio_contract = deepcopy(measurement_contract)
    ratio_cell = ratio_contract["cells"][0]
    ratio_cell["metric_definition"] = "Operating-profit margin is consolidated operating profit divided by consolidated operating revenue."
    ratio_cell["measurement_formula"] = {
        "formula_kind": "RATIO",
        "numerator_field_id": "FIELD:CONSOLIDATED_OPERATING_PROFIT",
        "denominator_field_id": "FIELD:CONSOLIDATED_OPERATING_REVENUE",
    }
    ratio_observations = deepcopy(observations)
    ratio_observation_id = settlement["dimension_settlements"][0]["outcome_observation_ref"]["observation_id"]
    ratio_measurement = ratio_observations[ratio_observation_id]["realized_measurement"]
    ratio_measurement["numeric_value"] = 0.25
    ratio_measurement["source_components"] = [
        {
            "source_id": "OUTCOME:SYNTHETIC:ANNUAL:2022",
            "source_url": "https://static.cninfo.com.cn/finalpage/synthetic/outcome-2022.PDF",
            "source_available_at": "2022-03-31T00:00:00+00:00",
            "field_id": "FIELD:CONSOLIDATED_OPERATING_PROFIT",
            "field_ref": "Synthetic official outcome annual report PDF p42.",
            "official_source_type": "OFFICIAL_ANNUAL_REPORT",
            "issuer_id": v3["issuer_id"],
            "responsibility_boundary": ratio_cell["responsibility_boundary"],
            "unit": ratio_cell["unit"],
            "outcome_period_end": ratio_cell["outcome_period_end"],
            "numeric_value": 25.0,
        },
        {
            "source_id": "OUTCOME:SYNTHETIC:ANNUAL:2022",
            "source_url": "https://static.cninfo.com.cn/finalpage/synthetic/outcome-2022.PDF",
            "source_available_at": "2022-03-31T00:00:00+00:00",
            "field_id": "FIELD:CONSOLIDATED_OPERATING_REVENUE",
            "field_ref": "Synthetic official outcome annual report PDF p43.",
            "official_source_type": "OFFICIAL_ANNUAL_REPORT",
            "issuer_id": v3["issuer_id"],
            "responsibility_boundary": ratio_cell["responsibility_boundary"],
            "unit": ratio_cell["unit"],
            "outcome_period_end": ratio_cell["outcome_period_end"],
            "numeric_value": 100.0,
        },
    ]
    ratio_settlement = deepcopy(settlement)
    ratio_settlement["dimension_settlements"][0]["realized_label"] = pit.NON_RISK_LABELS[1]
    ratio_result = pit.settle_company_state_forecast(
        v3, ratio_settlement, measurement_contract=ratio_contract, observation_receipts=ratio_observations,
    )
    assert ratio_result["valid"]

    formula_drift = deepcopy(ratio_observations)
    formula_drift[ratio_observation_id]["realized_measurement"]["numeric_value"] = 0.20
    rejected = pit.settle_company_state_forecast(
        v3, ratio_settlement, measurement_contract=ratio_contract, observation_receipts=formula_drift,
    )
    assert not rejected["valid"]
    assert (
        "settlement.dimension_settlements[0].realized_measurement.numeric_value_must_follow_measurement_formula"
        in rejected["findings"]
    )

    component_page_drift = deepcopy(ratio_observations)
    component_page_drift[ratio_observation_id]["realized_measurement"]["source_components"][1]["field_ref"] = "Unpaged synthetic field."
    rejected = pit.settle_company_state_forecast(
        v3, ratio_settlement, measurement_contract=ratio_contract, observation_receipts=component_page_drift,
    )
    assert not rejected["valid"]
    assert (
        "settlement.dimension_settlements[0].realized_measurement.source_components[1].field_ref_must_be_paged_reference"
        in rejected["findings"]
    )

    label_drift = deepcopy(settlement)
    label_drift["dimension_settlements"][0]["realized_label"] = pit.NON_RISK_LABELS[2]
    rejected = pit.settle_company_state_forecast(
        v3, label_drift, measurement_contract=measurement_contract, observation_receipts=observations,
    )
    assert not rejected["valid"]
    assert "settlement.dimension_settlements[0].realized_label_must_follow_measurement_contract_thresholds" in rejected["findings"]

    period_drift = deepcopy(settlement)
    observation_drift = deepcopy(observations)
    first_observation = period_drift["dimension_settlements"][0]["outcome_observation_ref"]["observation_id"]
    observation_drift[first_observation]["realized_measurement"]["outcome_period_end"] = "2022-12-31"
    rejected = pit.settle_company_state_forecast(
        v3, period_drift, measurement_contract=measurement_contract, observation_receipts=observation_drift,
    )
    assert not rejected["valid"]
    assert "settlement.dimension_settlements[0].realized_measurement.outcome_period_end_must_match_measurement_contract" in rejected["findings"]

    late_contract = deepcopy(measurement_contract)
    late_contract["cells"][0]["outcome_period_end"] = "2020-01-01"
    rejected = pit.validate_forecast_outcome_measurement_contract(late_contract)
    assert not rejected["valid"]
    assert "measurement_contract.cells[0].outcome_period_end_must_follow_cutoff" in rejected["findings"]

    issuer_drift = deepcopy(observations)
    issuer_drift[first_observation]["issuer_id"] = "ISSUER:OTHER"
    rejected = pit.settle_company_state_forecast(
        v3, settlement, measurement_contract=measurement_contract, observation_receipts=issuer_drift,
    )
    assert not rejected["valid"]
    assert (
        "settlement.dimension_settlements[0].observation:outcome_observation.issuer_id_must_match_frozen_forecast"
        in rejected["findings"]
    )

    source_issuer_drift = deepcopy(observations)
    source_issuer_drift[first_observation]["outcome_source"]["issuer_id"] = "ISSUER:OTHER"
    rejected = pit.settle_company_state_forecast(
        v3, settlement, measurement_contract=measurement_contract, observation_receipts=source_issuer_drift,
    )
    assert not rejected["valid"]
    assert (
        "settlement.dimension_settlements[0].observation:outcome_observation.outcome_source.issuer_id_must_match_frozen_forecast"
        in rejected["findings"]
    )

    source_artifact_drift = deepcopy(observations)
    source_artifact_drift[first_observation]["outcome_source"]["source_url"] = "http://untraceable.example/outcome.pdf"
    rejected = pit.settle_company_state_forecast(
        v3, settlement, measurement_contract=measurement_contract, observation_receipts=source_artifact_drift,
    )
    assert not rejected["valid"]
    assert (
        "settlement.dimension_settlements[0].observation:outcome_observation.outcome_source.source_url_must_be_https_official_artifact"
        in rejected["findings"]
    )

    late_source = deepcopy(observations)
    late_source[first_observation]["outcome_source"]["source_available_at"] = "2022-04-02T00:00:00+00:00"
    rejected = pit.settle_company_state_forecast(
        v3, settlement, measurement_contract=measurement_contract, observation_receipts=late_source,
    )
    assert not rejected["valid"]
    assert (
        "settlement.dimension_settlements[0].outcome_source_cannot_follow_settlement"
        in rejected["findings"]
    )

    raw_redeclaration = deepcopy(settlement)
    raw_redeclaration["dimension_settlements"][0]["outcome_source"] = deepcopy(
        observations[first_observation]["outcome_source"],
    )
    rejected = pit.settle_company_state_forecast(
        v3, raw_redeclaration, measurement_contract=measurement_contract, observation_receipts=observations,
    )
    assert not rejected["valid"]
    assert (
        "settlement.dimension_settlements[0].v3_must_reference_observation_not_redeclare_raw_field"
        in rejected["findings"]
    )


def test_legacy_forecasts_remain_unscored_even_when_a_later_source_exists() -> None:
    universe, h1 = _universe_and_h1()
    v1 = _forecast(universe, h1, universe["members"][0]["company_id"])
    rejected = pit.settle_company_state_forecast(v1, _observed_settlement(v1))
    assert not rejected["valid"]
    assert "settlement.dimension_settlements[0].legacy_forecast_must_remain_unscored" in rejected["findings"]


def test_v3_measurement_mismatch_is_a_custodian_receipted_coverage_state() -> None:
    universe, h1 = _universe_and_h1()
    v2 = _forecast(
        universe, h1, universe["members"][0]["company_id"],
        decision_contract_ref={"contract_id": "DC:SYNTHETIC:FORECAST:V1", "contract_version": 1},
    )
    from tests.test_judgment_training_decision_contract import _contract
    decision_contract = _contract(v2)
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    v3 = _v3_forecast(v2, measurement_contract)
    settlement = _v3_observed_settlement(v3, measurement_contract)
    observations = _v3_observation_receipts(v3, measurement_contract)
    first_entry = settlement["dimension_settlements"][0]
    observation_id = first_entry["outcome_observation_ref"]["observation_id"]
    first_entry["status"] = "MEASUREMENT_MISMATCH"
    first_entry["realized_label"] = None
    receipt = observations[observation_id]
    receipt["observation_status"] = "MEASUREMENT_MISMATCH"
    receipt.pop("realized_measurement")
    receipt["mismatch_rule"] = measurement_contract["cells"][0]["mismatch_rules"][0]
    receipt["mismatch_detail"] = "The disclosed result reports a different consolidated perimeter."
    receipt["outcome_source"]["source_field_id"] = "FIELD:DISCLOSED:DIFFERENT:PERIMETER"
    result = pit.settle_company_state_forecast(
        v3, settlement, measurement_contract=measurement_contract, observation_receipts=observations,
    )
    assert result["valid"], result["findings"]
    assert result["coverage"]["observed_scored_cells"] == 17

    wrong_receipt_status = deepcopy(observations)
    wrong_receipt_status[observation_id]["observation_status"] = "OBSERVED_MEASUREMENT"
    wrong_receipt_status[observation_id]["realized_measurement"] = {
        "measurement_id": measurement_contract["cells"][0]["measurement_id"],
        "measurement_kind": measurement_contract["cells"][0]["measurement_kind"],
        "unit": measurement_contract["cells"][0]["unit"],
        "outcome_period_end": measurement_contract["cells"][0]["outcome_period_end"],
        "responsibility_boundary": measurement_contract["cells"][0]["responsibility_boundary"],
        "numeric_value": 0.0,
    }
    wrong_receipt_status[observation_id].pop("mismatch_rule")
    wrong_receipt_status[observation_id].pop("mismatch_detail")
    rejected = pit.settle_company_state_forecast(
        v3, settlement, measurement_contract=measurement_contract, observation_receipts=wrong_receipt_status,
    )
    assert not rejected["valid"]
    assert "settlement.dimension_settlements[0].observation_receipt_must_record_measurement_mismatch" in rejected["findings"]

    uncontracted_reason = deepcopy(observations)
    uncontracted_reason[observation_id]["mismatch_rule"] = "An invented post-freeze mismatch reason."
    rejected = pit.settle_company_state_forecast(
        v3, settlement, measurement_contract=measurement_contract, observation_receipts=uncontracted_reason,
    )
    assert not rejected["valid"]
    assert (
        "settlement.dimension_settlements[0].observation:outcome_observation.mismatch_rule_must_be_frozen_in_measurement_contract"
        in rejected["findings"]
    )

    v2 = _forecast(
        universe, h1, universe["members"][0]["company_id"],
        decision_contract_ref={"contract_id": "DC:SYNTHETIC:FORECAST:V1", "contract_version": 1},
    )
    rejected = pit.settle_company_state_forecast(v2, _observed_settlement(v2))
    assert not rejected["valid"]
    assert "settlement.dimension_settlements[0].legacy_forecast_must_remain_unscored" in rejected["findings"]


def test_outcome_observation_cannot_acquire_a_dimension_the_frozen_forecast_excluded() -> None:
    universe, h1 = _universe_and_h1()
    v2 = _forecast(
        universe, h1, universe["members"][0]["company_id"],
        decision_contract_ref={"contract_id": "DC:SYNTHETIC:FORECAST:V1", "contract_version": 1},
    )
    from tests.test_judgment_training_decision_contract import _contract

    decision_contract = _contract(v2)
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    v3 = _v3_forecast(v2, measurement_contract)
    excluded = deepcopy(v3)
    excluded["dimensions"][0]["evidence_status"] = "EVIDENCE_INELIGIBLE"
    observation = _v3_observation_receipts(v3, measurement_contract)[
        f"OBS:{v3['forecast_id']}:NORMAL_EARNINGS:ONE_YEAR"
    ]
    result = pit.validate_forecast_outcome_observation_receipt(
        observation, forecast=excluded, measurement_contract=measurement_contract,
    )
    assert not result["valid"]
    assert "outcome_observation.cannot_observe_unforecast_dimension" in result["findings"]


def test_relative_tournament_is_dimension_specific_reference_not_causal_panel() -> None:
    universe, h1 = _universe_and_h1()
    company_ids = [member["company_id"] for member in h1["members"]
                   if member["final_peer_panel_disposition"] == "PENDING_ACTION_WINDOW_REVIEW"]
    forecasts = [_forecast(universe, h1, company_id) for company_id in company_ids]
    for forecast in forecasts:
        assert pit.validate_company_state_forecast(forecast, universe_snapshot=universe, stage0_package=h1)["valid"]
    tournament = {
        "schema_version": pit.TOURNAMENT_SCHEMA_VERSION,
        "tournament_id": "TOURNAMENT:SYNTHETIC:2020",
        "forecast_epoch_id": pit.FORECAST_EPOCH_ID,
        "cutoff_at": universe["cutoff_at"],
        "universe_id": universe["universe_id"],
        "source_packet_refs": [H1_REF],
        "ranked_company_ids": company_ids,
        "forecast_ids": [forecast["forecast_id"] for forecast in forecasts],
        "dimension_rankings": [
            {
                "dimension_id": dimension_id,
                "ordered_company_ids": company_ids,
                "unranked_company_ids": [],
                "rationale": "Reference ordering only; it claims neither untreated controls nor an action effect.",
            }
            for dimension_id in pit.FORECAST_DIMENSIONS
        ],
        "object_class": "RELATIVE_TRAJECTORY_TOURNAMENT",
        "claim_class": "RELATIVE_TRAJECTORY_REFERENCE",
        "allowed_outputs": ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }
    result = pit.validate_relative_trajectory_tournament(
        tournament, forecasts=forecasts, universe_snapshot=universe, stage0_package=h1,
    )
    assert result["valid"], result["findings"]

    h1_with_break = deepcopy(h1)
    break_member = h1_with_break["members"][2]
    break_member["final_peer_panel_disposition"] = "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"
    break_forecast = forecasts[2]
    invalid = deepcopy(tournament)
    invalid["ranked_company_ids"] = [company_ids[0], break_member["company_id"]]
    invalid["forecast_ids"] = [forecasts[0]["forecast_id"], break_forecast["forecast_id"]]
    for ranking in invalid["dimension_rankings"]:
        ranking["ordered_company_ids"] = list(invalid["ranked_company_ids"])
    rejected = pit.validate_relative_trajectory_tournament(
        invalid, forecasts=[forecasts[0], break_forecast], universe_snapshot=universe, stage0_package=h1_with_break,
    )
    assert not rejected["valid"]
    assert "tournament.scope_or_control_break_cannot_enter_relative_reference" in rejected["findings"]


def _observed_settlement(forecast: dict) -> dict:
    entries = []
    for dimension in forecast["dimensions"]:
        labels = pit.RISK_LABELS if dimension["dimension_id"] == "PERMANENT_LOSS_RISK" else pit.NON_RISK_LABELS
        for window_id in pit.FORECAST_WINDOWS:
            entries.append({
                "dimension_id": dimension["dimension_id"],
                "window_id": window_id,
                "status": "OBSERVED",
                "realized_label": labels[1],
                "outcome_source": {
                    "source_id": "OUTCOME:SYNTHETIC:ANNUAL:2022",
                    "source_available_at": "2022-03-31T00:00:00+00:00",
                    "field_ref": "Synthetic official outcome annual report PDF p42.",
                },
            })
    return {
        "schema_version": pit.SETTLEMENT_SCHEMA_VERSION,
        "settlement_id": "SETTLEMENT:SYNTHETIC:2022",
        "forecast_id": forecast["forecast_id"],
        "company_id": forecast["company_id"],
        "cutoff_at": forecast["cutoff_at"],
        "settled_at": "2022-04-01T00:00:00+00:00",
        "custodian_id": "SYNTHETIC:CUSTODIAN",
        "outcome_access_authorized": True,
        "dimension_settlements": entries,
        "object_class": "FORECAST_SETTLEMENT",
        "claim_class": "PREQUENTIAL_FEEDBACK",
        "allowed_outputs": ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }


def _outcome_measurement_contract(forecast: dict, decision_contract: dict, *, policy_change_ids: list[str] | None = None) -> dict:
    periods = {"ONE_YEAR": "2021-12-31", "THREE_YEAR": "2023-12-31", "FIVE_YEAR": "2025-12-31"}
    cells = []
    for dimension_id in pit.FORECAST_DIMENSIONS:
        labels = pit.RISK_LABELS if dimension_id == "PERMANENT_LOSS_RISK" else pit.NON_RISK_LABELS
        for window_id in pit.FORECAST_WINDOWS:
            forecast_dimension = next(item for item in forecast["dimensions"] if item["dimension_id"] == dimension_id)
            forecast_window = next(item for item in forecast_dimension["forecast_by_window"] if item["window_id"] == window_id)
            cell = {
                "dimension_id": dimension_id,
                "window_id": window_id,
                "measurement_id": f"MEASURE:{forecast['company_id']}:{dimension_id}:{window_id}",
                "outcome_period_end": periods[window_id],
                "responsibility_boundary": f"ISSUER_CONSOLIDATED:{forecast['issuer_id']}",
                "unit": "RATIO",
                "official_source_type": "OFFICIAL_ANNUAL_REPORT",
                "source_field_id": f"FIELD:{dimension_id}:{window_id}",
                "metric_definition": "A frozen synthetic annual-report measure used only to test the deterministic outcome mapping.",
                "mismatch_rules": ["Return MEASUREMENT_MISMATCH when the disclosed field does not share the frozen perimeter or unit."],
            }
            if "probabilities" in forecast_window:
                cell.update({
                    "measurement_kind": "ORDINAL_THRESHOLD", "lower_threshold": -1.0,
                    "upper_threshold": 1.0, "label_order": list(labels),
                    "measurement_formula": {"formula_kind": "DIRECT_NUMERIC", "value_field_id": f"FIELD:{dimension_id}:{window_id}"},
                })
            else:
                cell.update({
                    "measurement_kind": "BINARY_EVENT",
                    "event_definition": "The frozen cutoff-defined binary operating event is disclosed as having occurred.",
                })
            cells.append(cell)
    return {
        "schema_version": pit.OUTCOME_MEASUREMENT_CONTRACT_SCHEMA_VERSION,
        "measurement_contract_id": f"OMC:{forecast['company_id']}:V1",
        "measurement_contract_version": 1,
        "decision_contract_ref": {"contract_id": decision_contract["contract_id"], "contract_version": decision_contract["contract_version"]},
        "company_id": forecast["company_id"],
        "issuer_id": forecast["issuer_id"],
        "cutoff_at": forecast["cutoff_at"],
        "custodian_id": decision_contract["roles"]["outcome_custodian_id"],
        "applied_policy_change_ids": policy_change_ids or [],
        "cells": cells,
        "object_class": "FORECAST_OUTCOME_MEASUREMENT_CONTRACT",
        "claim_class": "PRE_OUTCOME_SETTLEMENT_DEFINITION",
        "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
    }


def _v3_forecast(forecast: dict, measurement_contract: dict) -> dict:
    item = deepcopy(forecast)
    item["schema_version"] = pit.FORECAST_SCHEMA_VERSION_V3
    item["forecast_epoch_id"] = pit.FORECAST_EPOCH_ID_V3
    item["forecast_id"] = f"{forecast['forecast_id']}:V3"
    item["outcome_measurement_contract_ref"] = {
        "measurement_contract_id": measurement_contract["measurement_contract_id"],
        "measurement_contract_version": measurement_contract["measurement_contract_version"],
    }
    item["applied_policy_change_ids"] = deepcopy(measurement_contract["applied_policy_change_ids"])
    return item


def _preforecast_evidence_receipt(forecast: dict, h1: dict) -> dict:
    """Cutoff-visible numeric extraction, deliberately separate from a forecast."""
    source = _source(h1, forecast["issuer_id"])
    return {
        "schema_version": pit.PREFORCAST_EVIDENCE_RECEIPT_SCHEMA_VERSION,
        "evidence_receipt_id": f"PREFORCAST:{forecast['company_id']}:V1",
        "evidence_receipt_version": 1,
        "h1_source_packet_ref": deepcopy(H1_REF),
        "company_id": forecast["company_id"],
        "issuer_id": forecast["issuer_id"],
        "cutoff_at": forecast["cutoff_at"],
        "curator_id": "SYNTHETIC:INDEPENDENT:PREFORECAST:CURATOR",
        "fields": [{
            "field_id": "FIELD:CONSOLIDATED:OPERATING_PROFIT",
            "source_id": source["source_id"],
            "source_url": source["url"],
            "source_type": source["source_type"],
            "published_at": source["published_at"],
            "period_end": source["period_end"],
            "issuer_id": source["issuer_id"],
            "responsibility_unit_id": source["responsibility_unit_id"],
            "perimeter_id": source["perimeter_id"],
            "unit": source["unit"],
            "field_ref": source["field_refs"][0],
            "numeric_value": 123.0,
            "label": "Consolidated operating profit disclosed in the H1-declared annual report.",
        }],
        "object_class": "PIT_PREFORCAST_EVIDENCE_RECEIPT",
        "claim_class": "CUTOFF_VISIBLE_FIELD_OBSERVATION",
        "allowed_outputs": ["FORECAST_EVIDENCE_ONLY"],
    }


def _curator_field_extraction(receipt: dict) -> dict:
    return {
        "schema_version": pit.CURATOR_FIELD_EXTRACTION_SCHEMA_VERSION,
        "shape": {
            "record_fields": [
                "source_id", "source_url", "published_at", "period_end", "issuer_id", "responsibility_unit_id",
                "perimeter_id", "unit", "field_id", "pdf_page_reference", "numeric_value", "label_zh",
            ],
            "additional_record_fields_permitted": False,
        },
        "unavailable_records": [],
        "records": [{
            "source_id": field["source_id"],
            "source_url": field["source_url"],
            "published_at": field["published_at"],
            "period_end": field["period_end"],
            "issuer_id": field["issuer_id"],
            "responsibility_unit_id": field["responsibility_unit_id"],
            "perimeter_id": field["perimeter_id"],
            "unit": field["unit"],
            "field_id": field["field_id"],
            "pdf_page_reference": field["field_ref"],
            "numeric_value": field["numeric_value"],
            "label_zh": field["label"],
        } for field in receipt["fields"]],
    }


def _v4_forecast(forecast: dict, measurement_contract: dict, evidence_receipt: dict) -> dict:
    item = _v3_forecast(forecast, measurement_contract)
    item["schema_version"] = pit.FORECAST_SCHEMA_VERSION_V4
    item["forecast_epoch_id"] = pit.FORECAST_EPOCH_ID_V4
    item["forecast_id"] = f"{forecast['forecast_id']}:V4"
    item["preforecast_evidence_receipt_ref"] = {
        "evidence_receipt_id": evidence_receipt["evidence_receipt_id"],
        "evidence_receipt_version": evidence_receipt["evidence_receipt_version"],
    }
    for dimension in item["dimensions"]:
        dimension["evidence_refs"][0]["field_id"] = evidence_receipt["fields"][0]["field_id"]
    return item


def _forecast_acquisition_scope(
    forecast: dict, measurement_contract: dict, *, included_dimensions: set[str] | None = None,
) -> dict:
    included = included_dimensions or set(pit.FORECAST_DIMENSIONS)
    return {
        "schema_version": pit.FORECAST_ACQUISITION_SCOPE_SCHEMA_VERSION,
        "scope_id": f"SCOPE:{forecast['company_id']}:V1",
        "scope_version": 1,
        "decision_contract_ref": deepcopy(forecast["decision_contract_ref"]),
        "outcome_measurement_contract_ref": {
            "measurement_contract_id": measurement_contract["measurement_contract_id"],
            "measurement_contract_version": measurement_contract["measurement_contract_version"],
        },
        "company_id": forecast["company_id"],
        "issuer_id": forecast["issuer_id"],
        "cutoff_at": forecast["cutoff_at"],
        "custodian_id": measurement_contract["custodian_id"],
        "cells": [
            {
                "dimension_id": cell["dimension_id"],
                "window_id": cell["window_id"],
                "measurement_id": cell["measurement_id"],
            }
            for cell in measurement_contract["cells"] if cell["dimension_id"] in included
        ],
        "object_class": "FORECAST_ACQUISITION_SCOPE",
        "claim_class": "PRE_OUTCOME_CUSTODIAN_COLLECTION_SCOPE",
        "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
    }


def _v5_forecast(
    forecast: dict, measurement_contract: dict, evidence_receipt: dict, acquisition_scope: dict,
) -> dict:
    item = _v4_forecast(forecast, measurement_contract, evidence_receipt)
    item["schema_version"] = pit.FORECAST_SCHEMA_VERSION_V5
    item["forecast_epoch_id"] = pit.FORECAST_EPOCH_ID_V5
    item["forecast_id"] = f"{forecast['forecast_id']}:V5"
    item["forecast_acquisition_scope_ref"] = {
        "scope_id": acquisition_scope["scope_id"],
        "scope_version": acquisition_scope["scope_version"],
    }
    return item


def _v6_forecast(
    forecast: dict, measurement_contract: dict, evidence_receipt: dict, acquisition_scope: dict, *, method_ref: dict,
) -> dict:
    item = _v5_forecast(forecast, measurement_contract, evidence_receipt, acquisition_scope)
    item["schema_version"] = pit.FORECAST_SCHEMA_VERSION_V6
    item["forecast_epoch_id"] = pit.FORECAST_EPOCH_ID_V6
    item["forecast_id"] = f"{forecast['forecast_id']}:V6"
    item["forecast_method_ref"] = deepcopy(method_ref)
    return item


def test_v4_forecast_requires_a_frozen_h1_bound_numeric_field_receipt() -> None:
    universe, h1 = _universe_and_h1()
    v2 = _forecast(
        universe, h1, universe["members"][0]["company_id"],
        decision_contract_ref={"contract_id": "DC:SYNTHETIC:FORECAST:V1", "contract_version": 1},
    )
    from tests.test_judgment_training_decision_contract import _contract
    decision_contract = _contract(v2)
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    evidence_receipt = _preforecast_evidence_receipt(v2, h1)
    assert pit.validate_preforecast_evidence_receipt(
        evidence_receipt, stage0_package=h1, h1_source_packet_ref=H1_REF,
    )["valid"]
    compiled = pit.compile_preforecast_evidence_receipt(
        _curator_field_extraction(evidence_receipt),
        evidence_receipt_id=evidence_receipt["evidence_receipt_id"],
        evidence_receipt_version=evidence_receipt["evidence_receipt_version"],
        h1_source_packet_ref=H1_REF,
        company_id=v2["company_id"], issuer_id=v2["issuer_id"], cutoff_at=v2["cutoff_at"],
        curator_id=evidence_receipt["curator_id"], stage0_package=h1,
    )
    assert compiled["valid"]
    assert compiled["evidence_receipt"] == evidence_receipt
    v4 = _v4_forecast(v2, measurement_contract, evidence_receipt)
    assert pit.validate_company_state_forecast(
        v4, universe_snapshot=universe, stage0_package=h1,
        preforecast_evidence_receipt=evidence_receipt,
    )["valid"]

    page_drift = deepcopy(evidence_receipt)
    page_drift["fields"][0]["field_ref"] = "Synthetic annual report field without an extractable page."
    rejected = pit.validate_preforecast_evidence_receipt(
        page_drift, stage0_package=h1, h1_source_packet_ref=H1_REF,
    )
    assert not rejected["valid"]
    assert "preforecast_evidence.fields[0].field_ref_must_be_paged_pdf_reference" in rejected["findings"]

    field_drift = deepcopy(v4)
    field_drift["dimensions"][0]["evidence_refs"][0]["field_id"] = "FIELD:UNDECLARED"
    rejected = pit.validate_company_state_forecast(
        field_drift, universe_snapshot=universe, stage0_package=h1,
        preforecast_evidence_receipt=evidence_receipt,
    )
    assert not rejected["valid"]
    assert "forecast.dimensions[0].preforecast_field_not_in_frozen_receipt" in rejected["findings"]

    role_drift = deepcopy(v4)
    role_drift["model_memory_mitigation"]["isolated_forecaster_id"] = evidence_receipt["curator_id"]
    rejected = pit.validate_company_state_forecast(
        role_drift, universe_snapshot=universe, stage0_package=h1,
        preforecast_evidence_receipt=evidence_receipt,
    )
    assert not rejected["valid"]
    assert "forecast.preforecast_curator_must_be_independent_from_isolated_forecaster" in rejected["findings"]

    identity_drift = deepcopy(evidence_receipt)
    identity_drift["company_id"] = "CN:NOT-IN-H1"
    rejected = pit.validate_preforecast_evidence_receipt(
        identity_drift, stage0_package=h1, h1_source_packet_ref=H1_REF,
    )
    assert not rejected["valid"]
    assert "preforecast_evidence.company_and_issuer_must_match_h1_risk_set_member" in rejected["findings"]

    source_drift = _curator_field_extraction(evidence_receipt)
    source_drift["records"][0]["source_id"] = "CNINFO:UNDECLARED"
    rejected = pit.compile_preforecast_evidence_receipt(
        source_drift,
        evidence_receipt_id=evidence_receipt["evidence_receipt_id"],
        evidence_receipt_version=1, h1_source_packet_ref=H1_REF,
        company_id=v2["company_id"], issuer_id=v2["issuer_id"], cutoff_at=v2["cutoff_at"],
        curator_id=evidence_receipt["curator_id"], stage0_package=h1,
    )
    assert not rejected["valid"]
    assert "curator_extraction.records[0].source_id_not_in_h1_static_packet" in rejected["findings"]


def test_v5_forecast_requires_a_preforecast_collection_scope_that_matches_forecastable_cells() -> None:
    universe, h1 = _universe_and_h1()
    v2 = _forecast(
        universe, h1, universe["members"][0]["company_id"],
        decision_contract_ref={"contract_id": "DC:SYNTHETIC:FORECAST:V1", "contract_version": 1},
    )
    from tests.test_judgment_training_decision_contract import _contract
    decision_contract = _contract(v2)
    measurement_contract = _outcome_measurement_contract(v2, decision_contract)
    evidence_receipt = _preforecast_evidence_receipt(v2, h1)
    scope = _forecast_acquisition_scope(v2, measurement_contract)
    assert pit.validate_forecast_acquisition_scope(scope, measurement_contract=measurement_contract)["valid"]
    v5 = _v5_forecast(v2, measurement_contract, evidence_receipt, scope)
    accepted = pit.validate_company_state_forecast(
        v5, universe_snapshot=universe, stage0_package=h1, preforecast_evidence_receipt=evidence_receipt,
        forecast_acquisition_scope=scope, outcome_measurement_contract=measurement_contract,
    )
    assert accepted["valid"], accepted["findings"]

    scope_missing_window = deepcopy(scope)
    scope_missing_window["cells"] = scope_missing_window["cells"][1:]
    rejected = pit.validate_forecast_acquisition_scope(scope_missing_window, measurement_contract=measurement_contract)
    assert not rejected["valid"]
    assert "acquisition_scope.NORMAL_EARNINGS_must_collect_all_forecast_windows" in rejected["findings"]

    forecast_excludes_dimension = deepcopy(v5)
    excluded = forecast_excludes_dimension["dimensions"][0]
    excluded["evidence_status"] = "EVIDENCE_INELIGIBLE"
    excluded["forecast_by_window"] = []
    rejected = pit.validate_company_state_forecast(
        forecast_excludes_dimension, universe_snapshot=universe, stage0_package=h1,
        preforecast_evidence_receipt=evidence_receipt, forecast_acquisition_scope=scope,
        outcome_measurement_contract=measurement_contract,
    )
    assert not rejected["valid"]
    assert "forecast.dimensions[0].acquisition_scope_cannot_collect_evidence_ineligible_dimension" in rejected["findings"]


def test_real_cn600585_v4_submission_is_closed_to_its_h1_packet_and_curated_fields() -> None:
    """Regression for the first evidence-bearing, model-memory-mitigated pilot.

    This is deliberately a pre-outcome validation: it loads neither a result
    source nor a settlement.  It ensures later code changes cannot turn the
    curator's fixed raw fields into an unbounded evidence channel.
    """
    cohort_dir = _REPO_ROOT / "docs" / "development" / "research" / "cohorts"
    h1 = json.loads((cohort_dir / "COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json").read_text(encoding="utf-8"))
    extraction = json.loads((cohort_dir / "PILOT_CN_CEMENT_20180430_CN600585_PREForecast_CURATOR_FIELD_EXTRACTION.json").read_text(encoding="utf-8"))
    forecast = json.loads((cohort_dir / "PILOT_CN_CEMENT_20180430_CN600585_FORECAST_V4_ISOLATED_SUBMISSION.json").read_text(encoding="utf-8"))
    h1_ref = {"receipt_id": "H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1", "receipt_version": 1}
    projection = history.project_stage0_h1_to_universe_and_carrier_seed(h1, h1_receipt_ref=h1_ref)
    assert projection["valid"], projection["findings"]
    receipt = pit.compile_preforecast_evidence_receipt(
        extraction,
        evidence_receipt_id="PREFORCAST:PILOT:CN:CEMENT:20180430:CN:600585:V1",
        evidence_receipt_version=1, h1_source_packet_ref=h1_ref,
        company_id="CN:600585", issuer_id="ISSUER:CN:600585", cutoff_at="2018-04-30T23:59:59+08:00",
        curator_id="CCU:CN600585:PREFORECAST:20260825", stage0_package=h1,
    )
    assert receipt["valid"], receipt["findings"]
    validation = pit.validate_company_state_forecast(
        forecast, universe_snapshot=projection["universe_snapshot"], stage0_package=h1,
        preforecast_evidence_receipt=receipt["evidence_receipt"],
    )
    assert validation["valid"], validation["findings"]
    dimensions = {item["dimension_id"]: item["evidence_status"] for item in forecast["dimensions"]}
    assert dimensions == {
        "NORMAL_EARNINGS": "MODEL_UNCERTAIN",
        "ROIC_OR_OPERATING_MARGIN": "MODEL_UNCERTAIN",
        "CASH_CONVERSION_AND_CAPEX_BURDEN": "MODEL_UNCERTAIN",
        "LEVERAGE_AND_FINANCIAL_RESILIENCE": "MODEL_UNCERTAIN",
        "COMPETITIVE_POSITION": "EVIDENCE_INELIGIBLE",
        "PERMANENT_LOSS_RISK": "EVIDENCE_INELIGIBLE",
    }


def _v3_observed_settlement(forecast: dict, measurement_contract: dict) -> dict:
    settlement = _observed_settlement(forecast)
    settlement["schema_version"] = pit.SETTLEMENT_SCHEMA_VERSION_V2
    settlement["settlement_id"] = f"{settlement['settlement_id']}:V3"
    settlement["outcome_measurement_contract_ref"] = {
        "measurement_contract_id": measurement_contract["measurement_contract_id"],
        "measurement_contract_version": measurement_contract["measurement_contract_version"],
    }
    for entry in settlement["dimension_settlements"]:
        dimension = next(item for item in forecast["dimensions"] if item["dimension_id"] == entry["dimension_id"])
        window = next(item for item in dimension["forecast_by_window"] if item["window_id"] == entry["window_id"])
        if "probabilities" not in window:
            entry["realized_label"] = True
        entry["outcome_observation_ref"] = {
            "observation_id": f"OBS:{forecast['forecast_id']}:{entry['dimension_id']}:{entry['window_id']}",
        }
        entry.pop("outcome_source")
    return settlement


def _v3_observation_receipts(forecast: dict, measurement_contract: dict) -> dict[str, dict]:
    cells = {(cell["dimension_id"], cell["window_id"]): cell for cell in measurement_contract["cells"]}
    receipts: dict[str, dict] = {}
    for dimension_id in pit.FORECAST_DIMENSIONS:
        for window_id in pit.FORECAST_WINDOWS:
            cell = cells[(dimension_id, window_id)]
            observation_id = f"OBS:{forecast['forecast_id']}:{dimension_id}:{window_id}"
            receipts[observation_id] = {
                "schema_version": pit.OUTCOME_OBSERVATION_RECEIPT_SCHEMA_VERSION,
                "observation_id": observation_id,
                "forecast_id": forecast["forecast_id"],
                "outcome_measurement_contract_ref": deepcopy(forecast["outcome_measurement_contract_ref"]),
                "company_id": forecast["company_id"],
                "issuer_id": forecast["issuer_id"],
                "cutoff_at": forecast["cutoff_at"],
                "custodian_id": "SYNTHETIC:CUSTODIAN",
                "observed_at": "2022-04-01T00:00:00+00:00",
                "dimension_id": dimension_id,
                "window_id": window_id,
                "observation_status": "OBSERVED_MEASUREMENT",
                "outcome_source": {
                    "source_id": "OUTCOME:SYNTHETIC:ANNUAL:2022",
                    "source_url": "https://static.cninfo.com.cn/finalpage/synthetic/outcome-2022.PDF",
                    "source_available_at": "2022-03-31T00:00:00+00:00",
                    "field_ref": "Synthetic official outcome annual report PDF p42.",
                    "source_field_id": cell["source_field_id"],
                    "official_source_type": cell["official_source_type"],
                    "issuer_id": forecast["issuer_id"],
                    "responsibility_boundary": cell["responsibility_boundary"],
                    "unit": cell["unit"],
                    "outcome_period_end": cell["outcome_period_end"],
                },
                "realized_measurement": {
                    "measurement_id": cell["measurement_id"],
                    "measurement_kind": cell["measurement_kind"],
                    "unit": cell["unit"],
                    "outcome_period_end": cell["outcome_period_end"],
                    "responsibility_boundary": cell["responsibility_boundary"],
                    "source_components": [{
                        "source_id": "OUTCOME:SYNTHETIC:ANNUAL:2022",
                        "source_url": "https://static.cninfo.com.cn/finalpage/synthetic/outcome-2022.PDF",
                        "source_available_at": "2022-03-31T00:00:00+00:00",
                        "field_id": cell["measurement_formula"]["value_field_id"] if cell["measurement_kind"] == "ORDINAL_THRESHOLD" else cell["source_field_id"],
                        "field_ref": "Synthetic official outcome annual report PDF p42.",
                        "official_source_type": cell["official_source_type"],
                        "issuer_id": forecast["issuer_id"],
                        "responsibility_boundary": cell["responsibility_boundary"],
                        "unit": cell["unit"],
                        "outcome_period_end": cell["outcome_period_end"],
                        "numeric_value": 0.0,
                    }],
                },
                "object_class": "FORECAST_OUTCOME_OBSERVATION_RECEIPT",
                "claim_class": "CUSTODIAN_EXTRACTED_OUTCOME_FIELD",
                "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
            }
            if cell["measurement_kind"] == "ORDINAL_THRESHOLD":
                receipts[observation_id]["realized_measurement"]["numeric_value"] = 0.0
            else:
                receipts[observation_id]["realized_measurement"]["boolean_value"] = True
                receipts[observation_id]["realized_measurement"].pop("source_components")
    return receipts


def _pairing(forecast: dict) -> dict:
    baseline_cells = []
    for dimension in forecast["dimensions"]:
        for window in dimension["forecast_by_window"]:
            cell = {"dimension_id": dimension["dimension_id"], "window_id": window["window_id"]}
            if "probabilities" in window:
                labels = pit.RISK_LABELS if dimension["dimension_id"] == "PERMANENT_LOSS_RISK" else pit.NON_RISK_LABELS
                cell["probabilities"] = [
                    {"label": labels[0], "probability": 0.5},
                    {"label": labels[1], "probability": 0.0},
                    {"label": labels[2], "probability": 0.5},
                ]
            else:
                cell["event_statement"] = window["event_statement"]
                cell["event_occurs_probability"] = 0.1
            baseline_cells.append(cell)
    return {
        "schema_version": pit.PAIRING_SCHEMA_VERSION,
        "pairing_id": f"PAIRING:{forecast['forecast_id']}",
        "forecast_id": forecast["forecast_id"],
        "company_id": forecast["company_id"],
        "cutoff_at": forecast["cutoff_at"],
        "task_contract_ref": "TASK:FORECAST:OPERATING_STATE:V1",
        "evidence_budget_id": "BUDGET:H1:ONE_PACKET:V1",
        "source_packet_refs": deepcopy(forecast["source_packet_refs"]),
        "baseline_method_id": "METHOD:SIMPLE:BASELINE:V1",
        "enhanced_method_id": "METHOD:TRAINING_ENHANCED:V1",
        "baseline_cells": baseline_cells,
        "object_class": "FORECAST_METHOD_PAIRING",
        "claim_class": "PAIRED_FORECAST_ABLATION",
        "allowed_outputs": ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }


def _paired_evaluation(forecast: dict, settlement: dict, pairing: dict) -> dict:
    return {
        "schema_version": pit.PAIRED_EVALUATION_SCHEMA_VERSION,
        "evaluation_id": f"EVALUATION:{forecast['forecast_id']}",
        "pairing_id": pairing["pairing_id"],
        "forecast_id": forecast["forecast_id"],
        "settlement_id": settlement["settlement_id"],
        "evaluated_at": "2022-04-02T00:00:00+00:00",
        "object_class": "FORECAST_PAIRED_EVALUATION",
        "claim_class": "PAIRED_METHOD_COMPARISON",
        "allowed_outputs": ["FORECAST_EVALUATION_ONLY", "RESEARCH_AGENDA"],
    }


def _attribution(forecast: dict, settlement: dict, *, scope: str = "CALIBRATION", evaluation: dict | None = None) -> dict:
    direct = scope in pit.DIRECT_FORECAST_LEARNING_SCOPES
    candidate = scope in pit.CANDIDATE_FORECAST_LEARNING_SCOPES
    locus = {
        "CALIBRATION": "CALIBRATION", "COVERAGE": "COVERAGE", "STATE_DEFINITION": "STATE_DEFINITION",
        "UNCERTAINTY_POLICY": "UNCERTAINTY", "BASELINE_PERFORMANCE": "BASELINE_PERFORMANCE",
        "EVIDENCE_PRIORITY": "EVIDENCE_PRIORITY", "RIVAL_HYPOTHESIS_METHOD": "RIVAL_HYPOTHESIS_METHOD",
    }.get(scope, "OUTCOME_MEASUREMENT")
    result = {
        "schema_version": pit.ATTRIBUTION_SCHEMA_VERSION,
        "attribution_id": f"ATTRIBUTION:{scope}:{forecast['forecast_id']}",
        "forecast_id": forecast["forecast_id"],
        "settlement_id": settlement["settlement_id"],
        "attributed_at": "2022-04-03T00:00:00+00:00",
        "reviewer_id": "SYNTHETIC:INDEPENDENT:CHALLENGER",
        "learning_scope": scope,
        "disposition": "DIRECT_FORECAST_POLICY" if direct else "CANDIDATE_REQUIRES_PAIRED_HOLDOUT" if candidate else "NOT_DIAGNOSTIC",
        "failure_locus": locus,
        "cell_refs": [{"dimension_id": "NORMAL_EARNINGS", "window_id": "ONE_YEAR"}],
        "object_class": "FORECAST_ERROR_ATTRIBUTION",
        "claim_class": "FORECAST_METHOD_FEEDBACK",
        "allowed_outputs": ["FORECAST_POLICY_ONLY", "RESEARCH_AGENDA"],
    }
    if scope != "NOT_DIAGNOSTIC":
        result["policy_change"] = {
            "change_id": f"POLICY:{scope}:V1",
            "statement": "Apply this narrowly-scoped forecast policy only after the attributed result became public.",
            "effective_from_cutoff_at": "2023-01-01T00:00:00+00:00",
        }
    if candidate and evaluation:
        result["paired_evaluation_id"] = evaluation["evaluation_id"]
        result["holdout"] = {
            "training_company_ids": ["CN:SYNTHETIC:TRAINING"],
            "holdout_company_ids": [forecast["company_id"]],
            "training_cutoff_through": "2019-12-31T23:59:59+00:00",
            "holdout_cutoff_from": "2020-01-01T00:00:00+00:00",
        }
    return result


def test_settlement_is_dimension_scored_with_coverage_and_prequential_time_gate() -> None:
    universe, h1 = _universe_and_h1()
    from tests.test_judgment_training_decision_contract import _contract
    v2 = _forecast(
        universe, h1, universe["members"][0]["company_id"],
        decision_contract_ref={"contract_id": "DC:SYNTHETIC:FORECAST:V1", "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, _contract(v2))
    forecast = _v3_forecast(v2, measurement_contract)
    settlement = _v3_observed_settlement(forecast, measurement_contract)
    observations = _v3_observation_receipts(forecast, measurement_contract)
    result = pit.settle_company_state_forecast(
        forecast, settlement, measurement_contract=measurement_contract, observation_receipts=observations,
    )
    assert result["valid"], result["findings"]
    assert len(result["dimension_scores"]) == 18
    assert result["coverage"]["selective_coverage"] == 1.0
    assert all(score["score"] and "brier" in score["score"] for score in result["dimension_scores"])

    late_observations = deepcopy(observations)
    first_id = settlement["dimension_settlements"][0]["outcome_observation_ref"]["observation_id"]
    late_observations[first_id]["outcome_source"]["source_available_at"] = "2025-03-31T00:00:00+00:00"
    rejected = pit.settle_company_state_forecast(
        forecast, settlement, measurement_contract=measurement_contract, observation_receipts=late_observations,
    )
    assert not rejected["valid"]
    assert "settlement.dimension_settlements[0].outcome_source_cannot_follow_settlement" in rejected["findings"]

    late_observation_receipt = deepcopy(observations)
    late_observation_receipt[first_id]["observed_at"] = "2025-03-31T00:00:00+00:00"
    rejected = pit.settle_company_state_forecast(
        forecast, settlement, measurement_contract=measurement_contract, observation_receipts=late_observation_receipt,
    )
    assert not rejected["valid"]
    assert "settlement.dimension_settlements[0].observation_receipt_cannot_follow_settlement" in rejected["findings"]

    binary_v2 = deepcopy(v2)
    binary_v2["forecast_id"] = "FORECAST:SYNTHETIC:BINARY:V2"
    for window in binary_v2["dimensions"][0]["forecast_by_window"]:
        window.pop("probabilities")
        window["event_statement"] = "The cutoff-defined earnings event occurs."
        window["event_occurs_probability"] = 0.6
    binary_contract = _outcome_measurement_contract(binary_v2, _contract(binary_v2))
    binary = _v3_forecast(binary_v2, binary_contract)
    binary_settlement = _v3_observed_settlement(binary, binary_contract)
    binary_observations = _v3_observation_receipts(binary, binary_contract)
    binary_result = pit.settle_company_state_forecast(
        binary, binary_settlement, measurement_contract=binary_contract, observation_receipts=binary_observations,
    )
    assert binary_result["valid"], binary_result["findings"]
    assert binary_result["dimension_scores"][0]["score"] == {"brier": 0.16000000000000003}


def test_forecast_learning_routes_direct_feedback_and_holds_method_changes_as_candidates() -> None:
    universe, h1 = _universe_and_h1()
    from tests.test_judgment_training_decision_contract import _contract
    v2 = _forecast(
        universe, h1, universe["members"][0]["company_id"],
        decision_contract_ref={"contract_id": "DC:SYNTHETIC:FORECAST:V1", "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, _contract(v2))
    forecast = _v3_forecast(v2, measurement_contract)
    settlement = _v3_observed_settlement(forecast, measurement_contract)
    observations = _v3_observation_receipts(forecast, measurement_contract)
    pairing = _pairing(forecast)
    assert pit.validate_forecast_pairing(pairing, forecast=forecast)["valid"]
    evaluation = _paired_evaluation(forecast, settlement, pairing)
    compared = pit.validate_forecast_paired_evaluation(
        evaluation, forecast=forecast, settlement=settlement, pairing=pairing,
        measurement_contract=measurement_contract, observation_receipts=observations,
    )
    assert compared["valid"], compared["findings"]
    assert len(compared["cell_comparisons"]) == 18
    assert all(item["enhanced_minus_baseline_brier"] < 0.0 for item in compared["cell_comparisons"])

    direct = _attribution(forecast, settlement)
    admitted = pit.validate_forecast_error_attribution(
        direct, forecast=forecast, settlement=settlement, measurement_contract=measurement_contract,
        observation_receipts=observations,
    )
    assert admitted["valid"], admitted["findings"]
    assert admitted["learning_authorization"] == "FORECAST_POLICY_DIRECT"

    candidate = _attribution(forecast, settlement, scope="EVIDENCE_PRIORITY", evaluation=evaluation)
    candidate_result = pit.validate_forecast_error_attribution(
        candidate, forecast=forecast, settlement=settlement, pairing=pairing, paired_evaluation=evaluation,
        measurement_contract=measurement_contract, observation_receipts=observations,
    )
    assert not candidate_result["valid"]
    assert "attribution.candidate_scope_requires_frozen_company_time_outcome_window_binding" in candidate_result["findings"]

    pairing_v2 = deepcopy(pairing)
    pairing_v2["schema_version"] = pit.PAIRING_SCHEMA_VERSION_V2
    pairing_v2["holdout_binding"] = {
        "program_id": "JTP:SYNTHETIC:FORECAST-HOLDOUT",
        "method_version": pairing_v2["enhanced_method_id"],
        "holdout_training_episode_id": "JTE:SYNTHETIC:FORECAST-HOLDOUT",
        "company_id": forecast["company_id"],
        "company_cluster_id": "COMPANY:SYNTHETIC:FORECAST-HOLDOUT",
        "cutoff_at": forecast["cutoff_at"],
        "outcome_not_before": "2022-01-01T00:00:00+00:00",
        "method_frozen_at": "2021-01-01T00:00:00+00:00",
        "method_freeze_recorded_at": "2021-01-01T00:01:00+00:00",
        "evaluated_cells": [{
            "dimension_id": "NORMAL_EARNINGS", "window_id": "ONE_YEAR", "outcome_period_end": "2021-12-31",
        }],
    }
    assert pit.validate_forecast_pairing(
        pairing_v2, forecast=forecast, measurement_contract=measurement_contract,
    )["valid"]
    evaluation_v2 = _paired_evaluation(forecast, settlement, pairing_v2)
    candidate_v2 = deepcopy(candidate)
    candidate_v2["paired_evaluation_id"] = evaluation_v2["evaluation_id"]
    candidate_v2.pop("holdout")
    candidate_result = pit.validate_forecast_error_attribution(
        candidate_v2, forecast=forecast, settlement=settlement, pairing=pairing_v2, paired_evaluation=evaluation_v2,
        measurement_contract=measurement_contract, observation_receipts=observations,
    )
    assert not candidate_result["valid"]
    assert "attribution.candidate_scope_requires_frozen_company_time_outcome_window_binding" in candidate_result["findings"]

    no_pair = deepcopy(candidate)
    no_pair.pop("paired_evaluation_id")
    no_pair.pop("holdout")
    rejected = pit.validate_forecast_error_attribution(
        no_pair, forecast=forecast, settlement=settlement, measurement_contract=measurement_contract,
        observation_receipts=observations,
    )
    assert not rejected["valid"]
    assert "attribution.candidate_scope_requires_paired_evaluation" in rejected["findings"]

    forbidden_output = deepcopy(direct)
    forbidden_output["allowed_outputs"] = ["FORECAST_POLICY_ONLY", "CJO", "INVESTMENT_INPUT"]
    rejected = pit.validate_forecast_error_attribution(
        forbidden_output, forecast=forecast, settlement=settlement, measurement_contract=measurement_contract,
        observation_receipts=observations,
    )
    assert not rejected["valid"]
    assert "attribution.allowed_outputs_must_exclude_cjo_report_and_investment" in rejected["findings"]


def test_abstention_and_unknown_outcomes_never_authorize_coverage_learning() -> None:
    universe, h1 = _universe_and_h1()
    from tests.test_judgment_training_decision_contract import _contract

    v2 = _forecast(
        universe, h1, universe["members"][0]["company_id"],
        decision_contract_ref={"contract_id": "DC:SYNTHETIC:FORECAST:V1", "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, _contract(v2))
    forecast = _v3_forecast(v2, measurement_contract)
    observed_settlement = _v3_observed_settlement(forecast, measurement_contract)

    abstained_forecast = deepcopy(forecast)
    for dimension in abstained_forecast["dimensions"]:
        dimension["evidence_status"] = "EVIDENCE_INELIGIBLE"
        dimension["forecast_by_window"] = []
    assert pit.validate_company_state_forecast(
        abstained_forecast, universe_snapshot=universe, stage0_package=h1,
    )["valid"]
    abstained_settlement = deepcopy(observed_settlement)
    for cell in abstained_settlement["dimension_settlements"]:
        cell["status"] = "EVIDENCE_INELIGIBLE"
        cell["realized_label"] = None
        cell.pop("outcome_observation_ref")
    settled = pit.settle_company_state_forecast(
        abstained_forecast, abstained_settlement, measurement_contract=measurement_contract,
    )
    assert settled["valid"], settled["findings"]
    assert settled["coverage"] == {
        "eligible_forecast_cells": 0,
        "observed_scored_cells": 0,
        "selective_coverage": None,
        "evidence_ineligible_cells": 18,
    }
    not_diagnostic = pit.validate_forecast_error_attribution(
        _attribution(abstained_forecast, abstained_settlement, scope="NOT_DIAGNOSTIC"),
        forecast=abstained_forecast, settlement=abstained_settlement,
        measurement_contract=measurement_contract,
    )
    assert not_diagnostic["valid"], not_diagnostic["findings"]
    assert not_diagnostic["learning_authorization"] == "NONE"

    false_coverage = pit.validate_forecast_error_attribution(
        _attribution(abstained_forecast, abstained_settlement, scope="COVERAGE"),
        forecast=abstained_forecast, settlement=abstained_settlement,
        measurement_contract=measurement_contract,
    )
    assert not false_coverage["valid"]
    assert false_coverage["learning_authorization"] == "NONE"
    assert "attribution.direct_scope_cell_status_not_eligible" in false_coverage["findings"]

    unknown_settlement = deepcopy(observed_settlement)
    for cell in unknown_settlement["dimension_settlements"]:
        cell["status"] = "UNKNOWN"
        cell["realized_label"] = None
        cell.pop("outcome_observation_ref")
    unknown = pit.validate_forecast_error_attribution(
        _attribution(forecast, unknown_settlement, scope="NOT_DIAGNOSTIC"),
        forecast=forecast, settlement=unknown_settlement, measurement_contract=measurement_contract,
    )
    assert unknown["valid"], unknown["findings"]
    assert unknown["learning_authorization"] == "NONE"


def test_local_abstention_does_not_block_observed_cell_calibration() -> None:
    universe, h1 = _universe_and_h1()
    from tests.test_judgment_training_decision_contract import _contract

    v2 = _forecast(
        universe, h1, universe["members"][0]["company_id"],
        decision_contract_ref={"contract_id": "DC:SYNTHETIC:FORECAST:V1", "contract_version": 1},
    )
    measurement_contract = _outcome_measurement_contract(v2, _contract(v2))
    forecast = _v3_forecast(v2, measurement_contract)
    loss_dimension = next(
        dimension for dimension in forecast["dimensions"] if dimension["dimension_id"] == "PERMANENT_LOSS_RISK"
    )
    loss_dimension["evidence_status"] = "EVIDENCE_INELIGIBLE"
    loss_dimension["forecast_by_window"] = []
    assert pit.validate_company_state_forecast(
        forecast, universe_snapshot=universe, stage0_package=h1,
    )["valid"]

    settlement = _v3_observed_settlement(_v3_forecast(v2, measurement_contract), measurement_contract)
    for cell in settlement["dimension_settlements"]:
        if cell["dimension_id"] == "PERMANENT_LOSS_RISK":
            cell["status"] = "EVIDENCE_INELIGIBLE"
            cell["realized_label"] = None
            cell.pop("outcome_observation_ref")
    observations = _v3_observation_receipts(forecast, measurement_contract)
    settled = pit.settle_company_state_forecast(
        forecast, settlement, measurement_contract=measurement_contract, observation_receipts=observations,
    )
    assert settled["valid"], settled["findings"]
    assert settled["coverage"]["eligible_forecast_cells"] == 15
    assert settled["coverage"]["observed_scored_cells"] == 15

    calibration = pit.validate_forecast_error_attribution(
        _attribution(forecast, settlement), forecast=forecast, settlement=settlement,
        measurement_contract=measurement_contract, observation_receipts=observations,
    )
    assert calibration["valid"], calibration["findings"]
    assert calibration["learning_authorization"] == "FORECAST_POLICY_DIRECT"


def test_company_and_time_holdout_and_shadow_episode_remain_separate_from_learning() -> None:
    universe, h1 = _universe_and_h1()
    forecast = _forecast(universe, h1, universe["members"][0]["company_id"])
    assert pit.validate_company_time_holdout(
        training_company_ids=["CN:SYNTHETIC:A"], holdout_company_ids=["CN:SYNTHETIC:B"],
        training_cutoff_through="2020-12-31T23:59:59+00:00", holdout_cutoff_from="2021-01-01T00:00:00+00:00",
    )["valid"]
    overlapping = pit.validate_company_time_holdout(
        training_company_ids=["CN:SYNTHETIC:A"], holdout_company_ids=["CN:SYNTHETIC:A"],
        training_cutoff_through="2020-12-31T23:59:59+00:00", holdout_cutoff_from="2020-12-31T23:59:59+00:00",
    )
    assert not overlapping["valid"]
    assert "holdout.company_axis_must_not_overlap_training" in overlapping["findings"]
    assert "holdout.time_axis_must_follow_training" in overlapping["findings"]

    shadow = {
        "schema_version": pit.SHADOW_SCHEMA_VERSION,
        "shadow_episode_id": "SHADOW:SYNTHETIC:2026",
        "forecast_epoch_id": pit.FORECAST_EPOCH_ID,
        "company_id": forecast["company_id"],
        "issuer_id": forecast["issuer_id"],
        "cutoff_at": forecast["cutoff_at"],
        "forecast_id": forecast["forecast_id"],
        "outcome_windows": list(pit.FORECAST_WINDOWS),
        "custodian_id": "SYNTHETIC:CUSTODIAN",
        "status": "WAITING_EXTERNAL_OUTCOME",
        "object_class": "PROSPECTIVE_SHADOW_EPISODE",
        "claim_class": "PREQUENTIAL_EVALUATION",
        "allowed_outputs": ["FORECAST_EVALUATION_ONLY"],
    }
    assert pit.validate_prospective_shadow_episode(shadow, forecast=forecast, now_at="2026-08-25T00:00:00+08:00")["valid"]

    root = Path(__file__).resolve().parents[1]
    with (root / "docs/development/research/cohorts/SHADOW_R05_SBUX_NA_TRANSACTION_DURABILITY_20260821.json").open(encoding="utf-8") as handle:
        signal_shadow = json.load(handle)
    assert pit.validate_prospective_signal_shadow_episode(
        signal_shadow, now_at="2026-08-25T00:00:00+08:00",
    )["valid"]
    expired_signal = deepcopy(signal_shadow)
    expired_signal["outcome_windows"][0]["resolution_due_at"] = "2026-08-24T00:00:00+08:00"
    rejected = pit.validate_prospective_signal_shadow_episode(expired_signal, now_at="2026-08-25T00:00:00+08:00")
    assert not rejected["valid"]
    assert "signal_shadow.must_have_unresolved_future_window_at_registration" in rejected["findings"]
    future_freeze = deepcopy(signal_shadow)
    future_freeze["source_freeze_ref"]["frozen_at"] = "2026-08-26T00:00:00+08:00"
    rejected = pit.validate_prospective_signal_shadow_episode(future_freeze, now_at="2026-08-25T00:00:00+08:00")
    assert not rejected["valid"]
    assert "signal_shadow.source_freeze_cannot_be_in_future_at_registration" in rejected["findings"]


def test_real_cement_isolated_submission_compiles_without_outcome_or_causal_permissions() -> None:
    root = Path(__file__).resolve().parents[1]
    with (root / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json").open(encoding="utf-8") as handle:
        h1 = json.load(handle)
    with (root / "docs/development/research/cohorts/PILOT_CN_CEMENT_20180430_ISOLATED_FORECAST_SUBMISSION.json").open(encoding="utf-8") as handle:
        submission = json.load(handle)
    h1_ref = {"receipt_id": "H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1", "receipt_version": 1}
    series = history.build_industry_history_series_from_h1(
        h1, h1_receipt_ref=h1_ref, cutoffs=["2018-04-30T23:59:59+08:00"],
    )
    assert series["valid"], series["findings"]
    universe = series["industry_history_series"]["snapshots"][0]
    compiled = pit.compile_isolated_forecast_submission(
        submission, universe_snapshot=universe, stage0_package=h1, h1_receipt_ref=h1_ref,
    )
    assert compiled["valid"], compiled["findings"]
    by_company = {forecast["company_id"]: forecast for forecast in compiled["forecasts"]}
    assert set(by_company) == {"CN:600585", "CN:600801", "CN:000401", "CN:600425", "CN:600802"}
    assert all(
        dimension["evidence_status"] == "EVIDENCE_INELIGIBLE"
        for dimension in by_company["CN:600801"]["dimensions"]
    )
    v2_refs = {
        company_id: {"contract_id": f"DC:PILOT:CN:CEMENT:20180430:{company_id}", "contract_version": 1}
        for company_id in by_company
    }
    compiled_v2 = pit.compile_isolated_forecast_submission(
        submission, universe_snapshot=universe, stage0_package=h1, h1_receipt_ref=h1_ref,
        decision_contract_refs=v2_refs,
    )
    assert compiled_v2["valid"], compiled_v2["findings"]
    assert {forecast["schema_version"] for forecast in compiled_v2["forecasts"]} == {pit.FORECAST_SCHEMA_VERSION_V2}
    assert {forecast["forecast_epoch_id"] for forecast in compiled_v2["forecasts"]} == {pit.FORECAST_EPOCH_ID_V2}
    assert all(forecast["forecast_id"].endswith(":V2") for forecast in compiled_v2["forecasts"])
    missing_contract = dict(v2_refs)
    missing_contract.pop("CN:600802")
    rejected = pit.compile_isolated_forecast_submission(
        submission, universe_snapshot=universe, stage0_package=h1, h1_receipt_ref=h1_ref,
        decision_contract_refs=missing_contract,
    )
    assert not rejected["valid"]
    assert "isolated_submission.decision_contract_refs_must_cover_h1_risk_set_exactly_once" in rejected["findings"]
    tournament = pit.compile_isolated_relative_tournament(
        submission, forecasts=compiled["forecasts"], universe_snapshot=universe, stage0_package=h1, h1_receipt_ref=h1_ref,
    )
    assert tournament["valid"], tournament["findings"]
    cash = next(item for item in tournament["tournament"]["dimension_rankings"] if item["dimension_id"] == "CASH_CONVERSION_AND_CAPEX_BURDEN")
    assert cash["ordered_company_ids"] == ["CN:600585", "CN:600802"]
    assert cash["unranked_company_ids"] == ["CN:600425"]
    v2_tournament = pit.compile_isolated_relative_tournament(
        submission, forecasts=compiled_v2["forecasts"], universe_snapshot=universe, stage0_package=h1, h1_receipt_ref=h1_ref,
    )
    assert v2_tournament["valid"], v2_tournament["findings"]
    assert v2_tournament["tournament"]["forecast_epoch_id"] == pit.FORECAST_EPOCH_ID_V2
    assert v2_tournament["tournament"]["tournament_id"].endswith(":V2")


def test_forecast_schema_covers_measurement_scope_tournament_and_custodian_access_authorization() -> None:
    schema = json.loads(Path("schemas/judgment_pit_forecast.schema.json").read_text(encoding="utf-8"))
    assert "forecast_outcome_access_authorization" in schema["$defs"]
    assert "forecast_outcome_measurement_contract" in schema["$defs"]
    assert "forecast_acquisition_scope" in schema["$defs"]
    assert pit.FORECAST_EPOCH_ID_V3 in schema["$defs"]["relative_trajectory_tournament"]["properties"]["forecast_epoch_id"]["enum"]
    assert pit.FORECAST_EPOCH_ID_V5 in schema["$defs"]["relative_trajectory_tournament"]["properties"]["forecast_epoch_id"]["enum"]
    assert schema["$defs"]["forecast_outcome_access_authorization"]["properties"]["allowed_outputs"]["const"] == pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS
