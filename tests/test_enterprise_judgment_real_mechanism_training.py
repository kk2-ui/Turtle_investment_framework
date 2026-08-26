from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path

from scripts import enterprise_judgment_real_mechanism_training as training
from scripts import enterprise_judgment_reconstruction_registry as reconstruction_registry


ROOT = Path(__file__).resolve().parents[1]
BLOCK_DIR = ROOT / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018"
ROUND5_PACKAGE_PATH = BLOCK_DIR / "26_round5_preoutcome_mechanism_package.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _selection_inputs() -> tuple[dict, dict, list[dict]]:
    block = _load(BLOCK_DIR / "04_industry_learning_block.json")
    freeze = _load(BLOCK_DIR / "04_pre_outcome_roster_freeze.json")
    receipts = [
        _load(BLOCK_DIR / "05_feedback_settlement_001.json"),
        _load(BLOCK_DIR / "07_feedback_settlement_002.json"),
        _load(BLOCK_DIR / "13_round2_continuation_feedback_settlement.json"),
        _load(BLOCK_DIR / "20_round3_feedback_settlement.json"),
        _load(BLOCK_DIR / "25_round4_contract_insufficiency_adjudication.json"),
    ]
    return block, freeze, receipts


def _atomic_cell(
    cell_id: str,
    *,
    layer: str,
    field_id: str,
    label_type: str,
) -> dict:
    event = label_type == "EVENT_PRESENCE"
    baseline_field_id = "" if event else field_id + ":BASELINE"
    formula_operator = "EVENT_BOOLEAN" if event else "PERCENT_CHANGE"
    ordered_labels = (
        ["MEASUREMENT_MISMATCH", "OBSERVED_YES", "OBSERVED_NO", "UNKNOWN"]
        if event
        else [
            "MEASUREMENT_MISMATCH",
            "OBSERVED_DECREASE",
            "OBSERVED_STABLE",
            "OBSERVED_INCREASE",
            "UNKNOWN",
        ]
    )
    return {
        "cell_id": cell_id,
        "thread_id": "THREAD:SYNTHETIC:PRIMARY",
        "layer": layer,
        "outcome_period": {
            "period_start": "2020-05-01T00:00:00+08:00",
            "period_end": "2020-12-31T23:59:59+08:00",
            "fiscal_period": "FY2020",
        },
        "responsibility_boundary": {
            "responsibility_unit_id": "ISSUER_CONSOLIDATED:CN:SYNTHETIC",
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "arena_id": "ARENA:SYNTHETIC",
            "scope_requirement": "same listed-company consolidated boundary",
        },
        "field_identity": {
            "outcome_field_id": field_id,
            "baseline_field_id": baseline_field_id,
            "statement_scope": "CONSOLIDATED",
            "table_or_note": "official annual report exact field",
            "line_item": field_id.rsplit(":", 1)[-1],
            "field_kind": "DISCLOSED_EVENT" if event else "AUDITED_FINANCIAL_LINE_ITEM",
        },
        "unit": {
            "kind": "BOOLEAN_EVENT" if event else "RMB",
            "currency": "NOT_APPLICABLE" if event else "RMB",
            "scale": "ONE",
        },
        "formula": {
            "operator": formula_operator,
            "input_field_ids": [field_id] if event else [baseline_field_id, field_id],
            "expression": "event is explicitly disclosed" if event else "(outcome - baseline) / abs(baseline)",
            "zero_baseline_rule": "NOT_APPLICABLE" if event else "RETURN_MEASUREMENT_MISMATCH",
        },
        "label_rule": {
            "type": label_type,
            "decrease_lte": None if event else -0.01,
            "increase_gte": None if event else 0.01,
            "ordered_labels": ordered_labels,
        },
        "conflict_rule": {
            "multiple_values": "MEASUREMENT_MISMATCH",
            "boundary_conflict": "MEASUREMENT_MISMATCH",
            "period_conflict": "MEASUREMENT_MISMATCH",
        },
        "unknown_rule": {
            "conditions": ["contract field is not disclosed after exhaustive contracted-source review"],
            "label": "UNKNOWN",
        },
        "mismatch_rule": {
            "conditions": ["field is disclosed only on a different period or responsibility boundary"],
            "label": "MEASUREMENT_MISMATCH",
            "propagation": "LOCAL_ONLY",
            "dependent_cell_ids": [],
        },
        "allowed_source_types": ["OFFICIAL_AUDITED_ANNUAL_REPORT"],
        "prohibited_inference": "Do not infer this atomic field from a sibling or aggregate narrative.",
    }


def _contract() -> dict:
    cells = [
        _atomic_cell(
            "CELL:SYNTHETIC:EXECUTION",
            layer="EXECUTED",
            field_id="FIELD:SYNTHETIC:EXECUTION_EVENT",
            label_type="EVENT_PRESENCE",
        ),
        _atomic_cell(
            "CELL:SYNTHETIC:SALES_VOLUME",
            layer="SALES_VOLUME",
            field_id="FIELD:SYNTHETIC:SALES_VOLUME",
            label_type="PERCENT_CHANGE_BAND",
        ),
        _atomic_cell(
            "CELL:SYNTHETIC:CASH",
            layer="CASH",
            field_id="FIELD:SYNTHETIC:OPERATING_CASH",
            label_type="PERCENT_CHANGE_BAND",
        ),
    ]
    return {
        "schema_version": training.CONTRACT_SCHEMA_VERSION,
        "contract_set_id": "OMC:SYNTHETIC:20200501:V1",
        "package_ref": "PACKAGE:SYNTHETIC:20200501:V1",
        "company_id": "CN:SYNTHETIC",
        "cutoff_at": "2020-05-01T00:00:00+08:00",
        "outcome_window": {
            "period_start": "2020-05-01T00:00:00+08:00",
            "period_end": "2020-12-31T23:59:59+08:00",
            "fiscal_period": "FY2020",
            "settlement_due_at": "2021-05-01T00:00:00+08:00",
        },
        "source_access": {
            "source_id": "SOURCE:SYNTHETIC:FY2020",
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "official_url": "https://static.example.invalid/fy2020.pdf",
            "published_after_cutoff": True,
            "access_state": "SEALED_UNTIL_PREOUTCOME_COMMIT",
            "custodian_access": "OUTCOME_ONLY",
        },
        "atomic_cells": cells,
        "thread_combination_rules": [
            {
                "rule_id": "COMBINE:SYNTHETIC:PRIMARY",
                "thread_id": "THREAD:SYNTHETIC:PRIMARY",
                "input_cell_ids": [cell["cell_id"] for cell in cells],
                "evaluation_order": [cell["cell_id"] for cell in cells],
                "rule": "Report every atomic label; do not collapse them into one mechanism verdict.",
                "conflict_rule": "Preserve conflicting and missing sibling labels without substitution.",
                "authorization": "TEACHING_ONLY_NO_CAUSAL_UPGRADE",
            }
        ],
        "rights": {
            "directional_learning": "NOT_AUTHORIZED",
            "enterprise_learning": "NOT_AUTHORIZED",
            "comparative": "NOT_AUTHORIZED",
            "cjo": "NOT_AUTHORIZED",
            "valuation": "NOT_AUTHORIZED",
            "report": "NOT_AUTHORIZED",
            "investment": "NOT_AUTHORIZED",
        },
        "allowed_outputs": ["OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"],
    }


def test_selection_is_derived_from_formal_receipts_and_immutable_roster() -> None:
    block, freeze, receipts = _selection_inputs()

    result = training.derive_receipt_backed_selection(block, freeze, receipts)

    assert result["valid"], result["findings"]
    selection = result["selection"]
    assert selection["selected_rank"] == 18
    assert selection["transition_id"] == "CCR:600802:20150415:20160427"
    assert selection["company_id"] == "CN:600802"
    assert selection["derived_completed_company_ids"] == [
        "CN:000401",
        "CN:600425",
        "CN:600585",
        "CN:600801",
    ]
    assert "CCR:600802:20140416:20150415" in selection["derived_consumed_transition_ids"]
    assert selection["selection_used_outcome"] is False
    assert selection["selection_used_lifecycle_label"] is False
    assert selection["selection_used_source_convenience"] is False


def test_selection_rejects_caller_claims_and_requires_formal_receipt_shapes() -> None:
    block, freeze, receipts = _selection_inputs()
    caller_claim = {
        "schema_version": "caller-completed-company-list.v1",
        "completed_company_ids": ["CN:600802"],
    }

    result = training.derive_receipt_backed_selection(block, freeze, receipts + [caller_claim])

    assert not result["valid"]
    assert result["selection"] is None
    assert "selection.receipts[5].unsupported_schema" in result["findings"]


def test_superseding_adjudication_consumes_only_the_invalid_transition() -> None:
    block, freeze, receipts = _selection_inputs()
    without_adjudication = training.derive_receipt_backed_selection(block, freeze, receipts[:-1])
    with_adjudication = training.derive_receipt_backed_selection(block, freeze, receipts)

    assert without_adjudication["selection"]["selected_rank"] == 17
    assert with_adjudication["selection"]["selected_rank"] == 18
    assert "CN:600802" not in with_adjudication["selection"]["derived_completed_company_ids"]


def test_atomic_measurement_contract_is_closed_and_mechanically_labeled() -> None:
    contract = _contract()

    result = training.validate_outcome_measurement_contract(contract)

    assert result["valid"], result["findings"]
    assert len(result["contract"]["atomic_cells"]) == 3
    assert all(
        cell["mismatch_rule"] == {
            "conditions": ["field is disclosed only on a different period or responsibility boundary"],
            "label": "MEASUREMENT_MISMATCH",
            "propagation": "LOCAL_ONLY",
            "dependent_cell_ids": [],
        }
        for cell in result["contract"]["atomic_cells"]
    )


def test_atomic_contract_rejects_missing_field_identity_and_ambiguous_label_order() -> None:
    contract = _contract()
    del contract["atomic_cells"][0]["field_identity"]["table_or_note"]
    contract["atomic_cells"][1]["label_rule"]["ordered_labels"].reverse()

    result = training.validate_outcome_measurement_contract(contract)

    assert not result["valid"]
    assert "measurement_contract.atomic_cells[0].field_identity.missing:table_or_note" in result["findings"]
    assert "measurement_contract.atomic_cells[1].ordered_labels_invalid" in result["findings"]


def test_one_synthetic_mismatch_does_not_block_observed_or_unknown_siblings() -> None:
    result = training.settle_synthetic_atomic_observations(
        _contract(),
        {
            "CELL:SYNTHETIC:EXECUTION": {"state": "MATCHED", "outcome": True},
            "CELL:SYNTHETIC:SALES_VOLUME": {"state": "MEASUREMENT_MISMATCH"},
            "CELL:SYNTHETIC:CASH": {"state": "UNKNOWN"},
        },
    )

    assert result["valid"], result["findings"]
    labels = {cell["cell_id"]: cell["label"] for cell in result["cell_results"]}
    assert labels == {
        "CELL:SYNTHETIC:EXECUTION": "OBSERVED_YES",
        "CELL:SYNTHETIC:SALES_VOLUME": "MEASUREMENT_MISMATCH",
        "CELL:SYNTHETIC:CASH": "UNKNOWN",
    }
    assert all(cell["mismatch_propagation"] == "LOCAL_ONLY" for cell in result["cell_results"])
    assert set(result["rights"].values()) == {"NOT_AUTHORIZED"}


def test_production_builder_has_no_caller_connection_or_private_compiler_surface() -> None:
    assert tuple(inspect.signature(reconstruction_registry.register_canonical_from_artifacts).parameters) == (
        "source_packet_receipt",
        "decision_contract",
        "enterprise_model",
        "decision_ledger",
        "spec",
        "frozen_at",
    )
    assert tuple(inspect.signature(training.register_and_project_preoutcome_package).parameters) == (
        "package",
        "block",
        "roster_freeze",
        "receipts",
        "frozen_at",
    )
    source = inspect.getsource(training.register_and_project_preoutcome_package)
    assert "sqlite3" not in source
    assert "_compile_" not in source
    assert "register_canonical_from_artifacts" in source
    assert "compile_mechanism_thread_projection" in source
    assert "compile_forecast_projection" in source


def test_atomic_mismatch_cannot_be_configured_to_invalidate_a_sibling() -> None:
    contract = _contract()
    contract["atomic_cells"][1]["mismatch_rule"]["dependent_cell_ids"] = [
        "CELL:SYNTHETIC:CASH"
    ]

    result = training.validate_outcome_measurement_contract(contract)

    assert not result["valid"]
    assert "measurement_contract.atomic_cells[1].atomic_cell_cannot_invalidate_siblings" in result["findings"]


def test_real_round5_package_is_receipt_derived_and_stops_before_outcome() -> None:
    block, freeze, receipts = _selection_inputs()
    package = _load(ROUND5_PACKAGE_PATH)

    result = training.validate_preoutcome_package(
        package,
        block=block,
        roster_freeze=freeze,
        receipts=receipts,
    )

    assert result["valid"], result["findings"]
    assert result["derived_selection"] == package["selection"]
    assert package["selection"]["selected_rank"] == 18
    assert package["selection"]["transition_id"] == "CCR:600802:20150415:20160427"
    assert package["sealed_outcome_source"] == {
        "source_id": "CNINFO:600802:ANN:20160426:1202245558",
        "access_state": "SEALED_UNTIL_PREOUTCOME_COMMIT",
        "outcome_content_read": False,
    }
    assert set(package["rights"].values()) == {"NOT_AUTHORIZED"}


def test_real_round5_contract_splits_the_mechanism_into_atomic_fields() -> None:
    package = _load(ROUND5_PACKAGE_PATH)
    contract = package["outcome_measurement_contract"]
    result = training.validate_outcome_measurement_contract(contract)

    assert result["valid"], result["findings"]
    cells = {cell["cell_id"]: cell for cell in contract["atomic_cells"]}
    assert len(cells) == 14
    assert {
        "EXECUTED",
        "CUSTOMER_RESPONSE",
        "SALES_VOLUME",
        "PRICE",
        "UNIT_COST",
        "SELLING_EXPENSE",
        "GROSS_MARGIN",
        "WORKING_CAPITAL",
        "CASH",
        "CAPITAL_BURDEN",
        "FINANCING",
        "PERMANENT_LOSS",
    } == {cell["layer"] for cell in cells.values()}
    assert cells["CELL:600802:20150415:CEMENT_SALES_VOLUME"]["field_identity"]["line_item"] == "cement sales volume"
    assert cells["CELL:600802:20150415:CLINKER_SALES_VOLUME"]["field_identity"]["line_item"] == "clinker sales volume"
    assert "production-line commissioning" in cells["CELL:600802:20150415:FURUN_OPERATING_SCOPE"]["prohibited_inference"]
    assert all(cell["mismatch_rule"]["propagation"] == "LOCAL_ONLY" for cell in cells.values())
    assert all(cell["mismatch_rule"]["dependent_cell_ids"] == [] for cell in cells.values())


def test_real_round5_j2_and_j3_bind_only_atomic_contract_cells() -> None:
    package = _load(ROUND5_PACKAGE_PATH)
    contract_ids = {
        cell["cell_id"]: "MC:" + cell["cell_id"].removeprefix("CELL:") + ":V2"
        for cell in package["outcome_measurement_contract"]["atomic_cells"]
    }
    episode_cells = {
        cell["outcome_cell_id"]: cell["measurement_contract_ref"]
        for cell in package["episode_manifest"]["outcome_cells"]
    }
    j2_cells = {
        cell_id
        for thread in package["mechanism_thread_set"]["threads"]
        for cell_id in thread["outcome_cell_refs"]
    }
    j3_cells = {
        cell["outcome_cell_id"]
        for thread in package["forecast_projection_source"]["threads"]
        for cell in thread["cells"]
    }

    assert episode_cells == contract_ids
    assert j2_cells == set(contract_ids)
    assert j3_cells <= set(contract_ids)
    assert package["forecast_projection_source"]["allowed_outputs"] == [
        "FORECAST_REQUESTS_ONLY",
        "RESEARCH_AGENDA",
    ]
