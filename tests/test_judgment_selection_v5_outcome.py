"""Synthetic-only tests for canonical V5 sealed-outcome reconstruction."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.judgment_selection_v5_outcome import (
    D4_REQUIRED_RAW_FIELDS,
    RESTRUCTURING_CASH_FIELD,
    resolve_v5_outcome,
)


ISSUERS = ("SYNV5:TARGET", "SYNV5:COMP:1", "SYNV5:COMP:2", "SYNV5:COMP:3")


def _d3(*, outcome: bool, direction: str) -> dict[str, float]:
    if not outcome:
        return {"revenue": 100.0, "operating_cost": 60.0}
    if direction == "A":
        return {"revenue": 120.0, "operating_cost": 65.0}  # 40 -> 55
    if direction == "B":
        return {"revenue": 100.0, "operating_cost": 70.0}  # 40 -> 30
    return {"revenue": 104.0, "operating_cost": 62.0}  # 40 -> 42


def _d4(*, outcome: bool, direction: str) -> dict[str, float]:
    ocf = 100.0 if not outcome else 130.0 if direction == "A" else 70.0 if direction == "B" else 102.0
    return {
        "cash_from_operating_activities": ocf,
        "cash_paid_for_all_long_lived_asset_purchases": 10.0,
        "beginning_accounts_receivable": 20.0,
        "beginning_prepayments": 0.0,
        "beginning_inventory": 20.0,
        "beginning_accounts_payable": 15.0,
        "beginning_contract_liabilities_or_customer_advances": 5.0,
        "ending_accounts_receivable": 20.0,
        "ending_prepayments": 0.0,
        "ending_inventory": 20.0,
        "ending_accounts_payable": 15.0,
        "ending_contract_liabilities_or_customer_advances": 5.0,
    }


def _threshold(operator: str, value: float) -> dict:
    return {"operator": operator, "value": value}


def _metrics(*, separate_restructuring: bool = False, out_of_perimeter: bool = False) -> list[dict]:
    d4_fields = list(D4_REQUIRED_RAW_FIELDS)
    treatment = "IN_OCF_NO_ADDITIONAL_DEDUCTION"
    if separate_restructuring:
        treatment = "SEPARATE_OPERATING_CASH_DEDUCTION"
        d4_fields.append(RESTRUCTURING_CASH_FIELD)
    if out_of_perimeter:
        treatment = "OUT_OF_PERIMETER_CANNOT_SETTLE"
    common = {
        "baseline_observation_matrix": {"periods": ["FY0"]},
        "primary_outcome_matrix": {"outcome_window_id": "SYNV5:WINDOW"},
        "baseline_period_id": "FY0",
        "primary_outcome_period_id": "FY1",
        "restatement_or_reclassification_policy": "INITIAL_ONLY",
        "discriminability": {
            "primary_threshold": _threshold("GTE", 5.0),
            "rival_threshold": _threshold("LTE", -5.0),
        },
    }
    return [
        common | {
            "metric_id": "SYNV5:D3",
            "clock": "D3",
            "formula_id": "D3_OPERATING_CONTRIBUTION_AMOUNT_V1",
            "economic_construct": "OPERATING_CONTRIBUTION_AMOUNT",
            "formula_and_ordered_raw_fields": ["revenue", "operating_cost"],
            "outcome_formula": {
                "formula_type": "LINEAR_COMBINATION",
                "terms": [
                    {"field_id": "revenue", "coefficient": 1.0},
                    {"field_id": "operating_cost", "coefficient": -1.0},
                ],
            },
        },
        common | {
            "metric_id": "SYNV5:D4",
            "clock": "D4",
            "formula_id": "D4_CONSERVATIVE_OWNER_CASH_V1",
            "economic_construct": "CONSERVATIVE_OWNER_CASH",
            "formula_and_ordered_raw_fields": d4_fields,
            "restructuring_cash_treatment": treatment,
        },
    ]


def _bundle(*, bridge: str = "NOT_REQUIRED", separate_restructuring: bool = False, out_of_perimeter: bool = False) -> dict:
    metrics = _metrics(separate_restructuring=separate_restructuring, out_of_perimeter=out_of_perimeter)
    matrix: list[dict] = []
    for metric in metrics:
        for issuer_id in ISSUERS:
            for period_id, role, period in (
                ("FY0", "BASELINE", {"start": "2019-01-01T00:00:00+00:00", "end": "2019-12-31T23:59:59+00:00"}),
                ("FY1", "PRIMARY_OUTCOME", {"start": "2020-01-01T00:00:00+00:00", "end": "2020-12-31T23:59:59+00:00"}),
            ):
                for field_id in metric["formula_and_ordered_raw_fields"]:
                    matrix.append({
                        "issuer_id": issuer_id,
                        "metric_id": metric["metric_id"],
                        "period_id": period_id,
                        "observation_role": role,
                        "field_id": field_id,
                        "economic_period": period,
                        "perimeter_id": "SYNV5:PERIMETER",
                        "currency_and_unit": "RMB_MILLION",
                        "field_locator": f"SYNV5:LOCATOR:{metric['metric_id']}:{field_id}",
                    })
    return {
        "schema_version": "judgment-selection-admission-v5.v1",
        "method_epoch_id": "JUDGMENT_SELECTION_ADMISSION_V5_2_COMPARATOR_PANEL",
        "selection_goal": "SELECTION",
        "selection_freeze_id": "SYNV5:FREEZE:001",
        "time_contract": {"research_cutoff_at": "2020-06-30T12:00:00+00:00"},
        "counterfactual_panel": {
            "target_issuer_id": ISSUERS[0],
            "members": [
                {"issuer_id": issuer_id, "causal_role": "EXTERNAL_SHOCK_COMPARATOR"}
                for issuer_id in ISSUERS[1:]
            ],
        },
        "measurement_contracts": metrics,
        "outcome_contract": {
            "frozen_raw_matrix": matrix,
            "fiscal_calendar_bridge": (
                {"status": "FROZEN", "bridge_id": "SYNV5:BRIDGE", "comparison_window_id": "SYNV5:WINDOW"}
                if bridge == "FROZEN" else {"status": "NOT_REQUIRED"}
            ),
        },
    }


def _receipts(*, target_d3: str = "A", target_d4: str = "A", separate_restructuring: bool = False) -> dict:
    cells: list[dict] = []
    for issuer_id in ISSUERS:
        d3_direction = target_d3 if issuer_id == ISSUERS[0] else "PEER"
        d4_direction = target_d4 if issuer_id == ISSUERS[0] else "PEER"
        values_by_metric = (
            ("D3", "SYNV5:D3", (("FY0", _d3(outcome=False, direction=d3_direction)), ("FY1", _d3(outcome=True, direction=d3_direction)))),
            ("D4", "SYNV5:D4", (("FY0", _d4(outcome=False, direction=d4_direction)), ("FY1", _d4(outcome=True, direction=d4_direction)))),
        )
        for clock, metric_id, by_period in values_by_metric:
            for period_id, fields in by_period:
                if separate_restructuring and clock == "D4":
                    fields = fields | {RESTRUCTURING_CASH_FIELD: 10.0}
                for field_id, value in fields.items():
                    cells.append({
                        "issuer_id": issuer_id,
                        "clock": clock,
                        "metric_id": metric_id,
                        "period_id": period_id,
                        "field_id": field_id,
                        "value": value,
                        "source": {
                            "source_id": f"SYNV5:{issuer_id}:{clock}:{period_id}:{field_id}",
                            "source_available_at": "2019-04-30T08:00:00+00:00" if period_id == "FY0" else "2021-04-30T08:00:00+00:00",
                            "availability_precision": "INTRADAY",
                            "filing_identity": "INITIAL",
                        },
                    })
    return {
        "schema_version": "judgment-v5-outcome-receipts.v1",
        "custodian_attestation": {"custodian_id": "SYNV5:CUSTODIAN", "research_side_outcome_exposure": "NONE"},
        "raw_cells": cells,
    }


def test_schema_refers_to_one_canonical_candidate_bundle_and_source_free_matrix() -> None:
    schema_path = Path(__file__).parents[1] / "schemas" / "judgment_v5_outcome_resolution.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    selection = schema["properties"]["selection_bundle"]
    assert selection["allOf"][0]["$ref"] == "judgment_selection_admission_v5.schema.json"
    matrix = schema["$defs"]["frozen_matrix_cell"]["properties"]
    assert "source" not in matrix and "source_id" not in matrix and "source_available_at" not in matrix
    assert {"issuer_id", "clock", "metric_id"} <= set(schema["$defs"]["raw_cell"]["properties"])
    assert "clock" not in matrix


def test_canonical_bundle_reconstructs_a_only_from_independent_d3_d4() -> None:
    result = resolve_v5_outcome(_bundle(), _receipts())
    assert result["valid"] is True
    assert result["resolution"]["status"] == "A_ONLY"
    assert result["resolution"]["metric_results"]["D3"]["target"]["delta"] == 15.0
    assert result["resolution"]["metric_results"]["D4"]["target"]["baseline"] == 90.0
    assert result["resolution"]["metric_results"]["D4"]["target"]["outcome"] == 120.0


def test_reconstructs_b_only_without_input_verdict() -> None:
    result = resolve_v5_outcome(_bundle(), _receipts(target_d3="B", target_d4="B"))
    assert result["valid"] is True
    assert result["resolution"]["status"] == "B_ONLY"


def test_opposite_d3_d4_results_are_mixed() -> None:
    result = resolve_v5_outcome(_bundle(), _receipts(target_d3="A", target_d4="B"))
    assert result["valid"] is True
    assert result["resolution"]["status"] == "MIXED"


def test_complete_matrix_without_discriminating_result_is_not_diagnostic() -> None:
    result = resolve_v5_outcome(_bundle(), _receipts(target_d3="PEER", target_d4="A"))
    assert result["valid"] is True
    assert result["resolution"]["status"] == "NOT_DIAGNOSTIC"


def test_missing_frozen_raw_field_is_unknown_without_replacing_peer() -> None:
    receipts = _receipts()
    receipts["raw_cells"] = [
        cell for cell in receipts["raw_cells"]
        if not (cell["issuer_id"] == "SYNV5:COMP:2" and cell["clock"] == "D4" and cell["period_id"] == "FY1" and cell["field_id"] == "ending_inventory")
    ]
    result = resolve_v5_outcome(_bundle(), receipts)
    assert result["valid"] is True
    assert result["resolution"]["status"] == "UNKNOWN"


def test_unfrozen_fiscal_difference_is_not_diagnostic() -> None:
    bundle = _bundle()
    for row in bundle["outcome_contract"]["frozen_raw_matrix"]:
        if row["issuer_id"] == "SYNV5:COMP:1" and row["period_id"] == "FY1":
            row["economic_period"] = {"start": "2020-04-01T00:00:00+00:00", "end": "2021-03-31T23:59:59+00:00"}
    result = resolve_v5_outcome(bundle, _receipts())
    assert result["valid"] is True
    assert result["resolution"]["status"] == "NOT_DIAGNOSTIC"


def test_frozen_fiscal_bridge_permits_predeclared_nonmatching_year_end() -> None:
    bundle = _bundle(bridge="FROZEN")
    for row in bundle["outcome_contract"]["frozen_raw_matrix"]:
        if row["issuer_id"] == "SYNV5:COMP:1" and row["period_id"] == "FY1":
            row["economic_period"] = {"start": "2020-04-01T00:00:00+00:00", "end": "2021-03-31T23:59:59+00:00"}
    result = resolve_v5_outcome(bundle, _receipts())
    assert result["valid"] is True
    assert result["resolution"]["status"] == "A_ONLY"


def test_early_arrow_rows_do_not_substitute_for_primary_outcome() -> None:
    bundle = _bundle()
    for issuer_id in ISSUERS:
        for field_id in ("revenue", "operating_cost"):
            bundle["outcome_contract"]["frozen_raw_matrix"].append({
                "issuer_id": issuer_id,
                "metric_id": "SYNV5:D3",
                "period_id": "FY0_SHORT",
                "observation_role": "EARLY_ARROW_NON_VOTER",
                "field_id": field_id,
                "economic_period": {"start": "2019-12-20T00:00:00+00:00", "end": "2019-12-31T23:59:59+00:00"},
                "perimeter_id": "SYNV5:PERIMETER",
                "currency_and_unit": "RMB_MILLION",
                "field_locator": f"SYNV5:LOCATOR:SYNV5:D3:{field_id}",
            })
    receipts = _receipts()
    for issuer_id in ISSUERS:
        for field_id, value in {"revenue": 1.0, "operating_cost": 1000.0}.items():
            receipts["raw_cells"].append({
                "issuer_id": issuer_id,
                "clock": "D3",
                "metric_id": "SYNV5:D3",
                "period_id": "FY0_SHORT",
                "field_id": field_id,
                "value": value,
                "source": {
                    "source_id": f"SYNV5:EARLY:{issuer_id}:{field_id}",
                    "source_available_at": "2021-04-30T08:00:00+00:00",
                    "availability_precision": "INTRADAY",
                    "filing_identity": "INITIAL",
                },
            })
    assert resolve_v5_outcome(bundle, receipts)["resolution"]["status"] == "A_ONLY"


def test_date_only_primary_source_at_cutoff_is_exposure_excluded() -> None:
    receipts = _receipts()
    primary = next(cell for cell in receipts["raw_cells"] if cell["period_id"] == "FY1")
    primary["source"]["source_available_at"] = "2020-06-30"
    primary["source"]["availability_precision"] = "DATE_ONLY"
    result = resolve_v5_outcome(_bundle(), receipts)
    assert result["valid"] is True
    assert result["resolution"]["status"] == "EXPOSURE_EXCLUDED"


def test_outcome_fact_invalidating_panel_is_boundary_captured() -> None:
    receipts = _receipts()
    receipts["boundary_facts"] = [{
        "boundary_kind": "PANEL",
        "reason": "A comparator has a material parallel action.",
        "source": {
            "source_id": "SYNV5:POST:PANEL",
            "source_available_at": "2021-04-30T08:00:00+00:00",
            "availability_precision": "INTRADAY",
            "filing_identity": "INITIAL",
        },
    }]
    result = resolve_v5_outcome(_bundle(), receipts)
    assert result["valid"] is True
    assert result["resolution"]["status"] == "BOUNDARY_CAPTURED"
    assert result["resolution"]["boundary_kinds"] == ["PANEL"]


def test_restatement_mismatch_is_measurement_boundary() -> None:
    receipts = _receipts()
    next(cell for cell in receipts["raw_cells"] if cell["period_id"] == "FY1")["source"]["filing_identity"] = "RESTATED"
    result = resolve_v5_outcome(_bundle(), receipts)
    assert result["valid"] is True
    assert result["resolution"]["status"] == "BOUNDARY_CAPTURED"
    assert result["resolution"]["boundary_kinds"] == ["MEASUREMENT"]


def test_separate_restructuring_cash_is_deducted_once() -> None:
    result = resolve_v5_outcome(_bundle(separate_restructuring=True), _receipts(separate_restructuring=True))
    assert result["valid"] is True
    assert result["resolution"]["status"] == "A_ONLY"
    assert result["resolution"]["metric_results"]["D4"]["target"]["baseline"] == 80.0
    assert result["resolution"]["metric_results"]["D4"]["target"]["outcome"] == 110.0


def test_out_of_perimeter_restructuring_cash_cannot_settle_d4() -> None:
    result = resolve_v5_outcome(_bundle(out_of_perimeter=True), _receipts())
    assert result["valid"] is True
    assert result["resolution"]["status"] == "BOUNDARY_CAPTURED"
    assert result["resolution"]["boundary_kinds"] == ["SCOPE"]


def test_old_wrapper_shape_is_not_an_adapter_path() -> None:
    bundle = _bundle()
    bundle["selection_freeze"] = {"selection_freeze_id": bundle.pop("selection_freeze_id")}
    result = resolve_v5_outcome(bundle, _receipts())
    assert result["valid"] is False
    assert "selection_bundle.selection_freeze_id_missing" in result["findings"]


def test_outcome_source_metadata_in_candidate_matrix_is_rejected() -> None:
    bundle = _bundle()
    bundle["outcome_contract"]["frozen_raw_matrix"][0]["source_id"] = "FORBIDDEN:OUTCOME"
    result = resolve_v5_outcome(bundle, _receipts())
    assert result["valid"] is False
    assert "outcome_contract_contains_noncanonical_or_outcome_source_metadata" in result["findings"]


def test_caller_outcome_score_and_researcher_exposure_are_refused() -> None:
    receipts = _receipts()
    receipts["score"] = 1.0
    result = resolve_v5_outcome(_bundle(), receipts)
    assert result["valid"] is False
    assert any("caller_supplied_derived_outcome" in finding for finding in result["findings"])
    receipts = _receipts()
    receipts["custodian_attestation"]["research_side_outcome_exposure"] = "CONFIRMED"
    assert resolve_v5_outcome(_bundle(), receipts)["valid"] is False
