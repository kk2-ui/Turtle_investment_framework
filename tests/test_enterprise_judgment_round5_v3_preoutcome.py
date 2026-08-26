from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path

import pytest

from scripts import enterprise_judgment_real_mechanism_training as training
from scripts import enterprise_judgment_reconstruction as reconstruction
from scripts import enterprise_judgment_training_control_plane as control
from scripts import outcome_measurement_acquisition as acquisition
from scripts import outcome_measurement_round5_adapter as round5
from scripts import outcome_measurement_settlement_adapter as settlement_adapter


ROOT = Path(__file__).resolve().parents[1]
BLOCK_DIR = ROOT / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018"
V2_PACKAGE = BLOCK_DIR / "26_round5_preoutcome_mechanism_package.json"
V3_PACKAGE = BLOCK_DIR / "29_round5_v3_preoutcome_mechanism_package.json"
CUSTODY_PROJECTION = BLOCK_DIR / "30_round5_v3_value_free_custody_projection.json"
CONTROL_RECEIPT = BLOCK_DIR / "31_round5_v3_preoutcome_control_plane_receipt.json"
FREEZE_AT = "2026-08-26T16:30:00+00:00"
RECEIPT_FILES = [
    "05_feedback_settlement_001.json",
    "07_feedback_settlement_002.json",
    "13_round2_continuation_feedback_settlement.json",
    "20_round3_feedback_settlement.json",
    "25_round4_contract_insufficiency_adjudication.json",
]


def _load(name_or_path: str | Path) -> dict:
    path = Path(name_or_path)
    if not path.is_absolute():
        path = BLOCK_DIR / path
    return json.loads(path.read_text(encoding="utf-8"))


def _receipt_refs(receipts: list[dict]) -> list[dict]:
    return [
        {
            "receipt_id": receipt.get("adjudication_id") or receipt["settlement_id"],
            "receipt_version": 1,
        }
        for receipt in receipts
    ]


def _register_selection_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[dict, list[dict]]:
    monkeypatch.setattr(reconstruction, "CANONICAL_REGISTRY_PATH", tmp_path / "canonical.db")
    block = _load("04_industry_learning_block.json")
    freeze = _load("04_pre_outcome_roster_freeze.json")
    receipts = [_load(name) for name in RECEIPT_FILES]
    assert control.register_roster_freeze(
        {"block": block, "roster_freeze": freeze}, registered_at="2026-08-26T16:20:00+00:00",
    )["registered"]
    for index, receipt in enumerate(receipts):
        assert control.register_selection_receipt(
            receipt, registered_at=f"2026-08-26T16:{21 + index:02d}:00+00:00",
        )["registered"]
    return {"freeze_id": freeze["freeze_id"]}, _receipt_refs(receipts)


def _v3_package() -> dict:
    return round5.build_round5_v3_package(_load(V2_PACKAGE), frozen_at=FREEZE_AT)


def test_committed_round5_v3_package_is_the_generated_valid_package() -> None:
    committed = _load(V3_PACKAGE)
    assert committed == _v3_package()
    assert committed["schema_version"] == training.PACKAGE_SCHEMA_VERSION_V3
    validation = training.validate_outcome_measurement_contract(committed["outcome_measurement_contract"])
    assert validation["valid"], validation["findings"]


def test_committed_custody_artifact_is_the_real_value_free_api_projection() -> None:
    package = _load(V3_PACKAGE)
    committed = _load(CUSTODY_PROJECTION)
    assert committed == round5.build_value_free_custody_projection(package)
    validation = round5.validate_value_free_custody_projection(committed, package=package)
    assert validation["valid"], validation["findings"]


def test_committed_control_receipt_replays_canonical_ids_and_keeps_outcome_sealed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    roster_ref, receipt_refs = _register_selection_inputs(monkeypatch, tmp_path)
    package = _load(V3_PACKAGE)
    receipt = _load(CONTROL_RECEIPT)
    result = training.register_and_project_preoutcome_package(
        package,
        roster_freeze_ref=roster_ref,
        receipt_refs=receipt_refs,
        frozen_at=FREEZE_AT,
    )

    assert result["valid"], result["findings"]
    produced = result["control_plane_receipt"]
    control_record = receipt["canonical_selection_control"]
    assert control_record["roster_freeze_ref"] == roster_ref
    assert control_record["formal_receipt_refs"] == receipt_refs
    for key, value in control_record["selection_result"].items():
        assert produced["selection"][key] == value
    assert produced["frozen_j1_ref"]["reconstruction_id"] == receipt["canonical_j1_registration"]["reconstruction_id"]
    contract_id = receipt["canonical_measurement_contract_registration"]["contract_set_id"]
    assert produced["canonical_measurement_contract_registration"]["contract_set_id"] == contract_id
    assert control.resolve_measurement_contract(contract_id) == package["outcome_measurement_contract"]
    resolved_bundle, resolved_receipts = control.resolve_canonical_selection_inputs(roster_ref, receipt_refs)
    assert resolved_bundle["roster_freeze"]["freeze_id"] == roster_ref["freeze_id"]
    assert _receipt_refs(resolved_receipts) == receipt_refs
    assert receipt["value_free_custody"]["generation_api"] == (
        "outcome_measurement_acquisition.build_value_free_custody_projection"
    )
    assert receipt["value_free_custody"]["submission_api"] == _load(CUSTODY_PROJECTION)["submission_api"]
    assert receipt["value_free_custody"]["settlement_api"] == _load(CUSTODY_PROJECTION)["settlement_api"]
    assert receipt["outcome_access"] == {
        "authorized": False,
        "content_read": False,
        "custodian_started": False,
        "settlement_created": False,
    }
    assert set(receipt["rights"].values()) == {"NOT_AUTHORIZED"}


def test_v3_contract_separates_cutoff_from_all_three_measurement_clocks() -> None:
    package = _v3_package()
    contract = package["outcome_measurement_contract"]
    result = training.validate_outcome_measurement_contract(contract)

    assert result["valid"], result["findings"]
    assert contract["outcome_window"]["period_start"] == "2015-01-01T00:00:00+08:00"
    assert contract["cutoff_at"] == "2015-04-15T00:00:00+08:00"
    cells = {cell["cell_id"]: cell for cell in contract["atomic_cells"]}
    assert {cell["measurement_clock"]["clock_kind"] for cell in cells.values()} == {
        "FLOW_PERIOD", "BALANCE_AS_OF", "EVENT_WINDOW",
    }
    assert cells["CELL:600802:20150415:OPERATING_CASH"]["measurement_clock"]["flow_period"] == {
        "period_start": "2015-01-01", "period_end": "2015-12-31", "fiscal_period": "FY2015",
    }
    assert cells["CELL:600802:20150415:ACCOUNTS_RECEIVABLE"]["measurement_clock"]["balance_as_of"]["as_of"] == "2015-12-31"
    assert cells["CELL:600802:20150415:CUSTOMER_RESPONSE_EVENT"]["measurement_clock"]["event_window"] == {
        "event_start": "2015-04-16", "event_end": "2015-12-31", "window_name": "POST_CUTOFF_FY2015_EVENT_WINDOW",
    }


def test_v3_derived_metrics_freeze_raw_inputs_units_conversions_and_complete_formulas() -> None:
    contract = _v3_package()["outcome_measurement_contract"]
    cells = {cell["cell_id"]: cell for cell in contract["atomic_cells"]}
    price = cells["CELL:600802:20150415:CEMENT_REALIZED_PRICE"]
    cost = cells["CELL:600802:20150415:CEMENT_UNIT_COST"]
    margin = cells["CELL:600802:20150415:CEMENT_GROSS_MARGIN"]

    assert price["formula"]["operator"] == "RATIO_CHANGE"
    assert price["formula"]["input_field_ids"] == [entry["field_id"] for entry in price["raw_input_fields"]]
    assert {entry["unit"] for entry in price["raw_input_fields"]} == {"RMB", "TONNE"}
    assert "FY2015_CEMENT_REVENUE_RMB / FY2015_CEMENT_SALES_VOLUME_TONNES" in price["formula"]["expression"]
    assert cost["formula"]["operator"] == "RATIO_CHANGE"
    assert "FY2015_CEMENT_OPERATING_COST_RMB / FY2015_CEMENT_SALES_VOLUME_TONNES" in cost["formula"]["expression"]
    assert margin["formula"]["operator"] == "DIFFERENCE"
    assert len(margin["raw_input_fields"]) == 4
    assert [item["field_id"] for item in margin["formula"]["unit_conversions"]] == margin["formula"]["input_field_ids"]


def test_canonical_resolver_selects_rank18_and_rejects_fake_receipts_or_inline_roster(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    roster_ref, receipt_refs = _register_selection_inputs(monkeypatch, tmp_path)
    package = _v3_package()
    result = training.validate_canonical_preoutcome_package(
        package, roster_freeze_ref=roster_ref, receipt_refs=receipt_refs,
    )
    assert result["valid"], result["findings"]
    assert result["derived_selection"]["selected_rank"] == 18

    fake = training.validate_canonical_preoutcome_package(
        package,
        roster_freeze_ref=roster_ref,
        receipt_refs=receipt_refs + [{"receipt_id": "FAKE:RECEIPT", "receipt_version": 1}],
    )
    assert not fake["valid"]
    assert fake["findings"][0].startswith("selection_receipt_not_registered:")

    inline = training.validate_canonical_preoutcome_package(
        package,
        roster_freeze_ref={"freeze_id": roster_ref["freeze_id"], "roster_freeze": {"company_cutoff_transition_ids": []}},
        receipt_refs=receipt_refs,
    )
    assert not inline["valid"]
    assert inline["findings"][0].startswith("roster_freeze_ref_invalid:")


def test_registered_v3_contract_rejects_post_freeze_mutation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(reconstruction, "CANONICAL_REGISTRY_PATH", tmp_path / "canonical.db")
    contract = _v3_package()["outcome_measurement_contract"]
    assert control.register_measurement_contract(contract, frozen_at=FREEZE_AT)["registered"]
    mutated = deepcopy(contract)
    mutated["atomic_cells"][0]["unknown_rule"]["conditions"].append("post-result mutation")
    with pytest.raises(control.TrainingControlPlaneError) as exc:
        control.register_measurement_contract(mutated, frozen_at=FREEZE_AT)
    assert exc.value.code == "measurement_contract_post_freeze_mutation"


def test_real_acquisition_api_builds_value_free_projection_and_public_settlement_delegates() -> None:
    package = _v3_package()
    projection = round5.build_value_free_custody_projection(package)

    assert projection["schema_version"] == "outcome-measurement-value-free-custody-projection.v1"
    assert projection["submission_api"] == "outcome_measurement_acquisition.validate_acquisition_result"
    assert projection["settlement_api"] == "outcome_measurement_settlement_adapter.register_acquisition_result"
    assert projection["outcome_access"] == {"authorized": False, "content_read": False, "custodian_started": False}
    assert len(projection["atomic_measurement_contracts"]) == 14
    encoded = json.dumps(projection, sort_keys=True).casefold()
    for forbidden in ("forecast_direction", "forecast_value", "probabilities", '"hypotheses"', '"j2"', '"j3"'):
        assert forbidden not in encoded
    assert inspect.getsource(round5.build_value_free_custody_projection).count("acquisition.build_value_free_custody_projection") == 1
    assert round5.settle_via_public_adapter.__doc__
    assert settlement_adapter.register_acquisition_result.__name__ == "register_acquisition_result"


def test_missing_event_cannot_be_submitted_as_observed_no() -> None:
    projection = round5.build_value_free_custody_projection(_v3_package())
    result = {
        "schema_version": acquisition.SCHEMA_VERSION,
        "measurement_contract_ref": {
            "measurement_contract_id": projection["measurement_contract_ref"]["contract_set_id"],
            "measurement_contract_version": 3,
        },
        "source_inventory_id": "INV:ROUND5:SEALED:V3",
        "custodian_id": projection["custodian_id"],
        "object_class": acquisition.OBJECT_CLASS,
        "claim_class": acquisition.CLAIM_CLASS,
        "allowed_outputs": ["FORECAST_OUTCOME_ACQUISITION_ONLY"],
        "observations": [{
            "measurement_id": "CELL:600802:20150415:CUSTOMER_RESPONSE_EVENT",
            "status": "UNKNOWN",
            "metric_id": "FIELD:600802:FY2015:DIRECT_CUSTOMER_RESPONSE_EVENT",
            "metric_definition": "Direct customer response event",
            "report_period_end": "2015-12-31",
            "unit": "BOOLEAN_EVENT",
            "currency": None,
            "reporting_scope": None,
            "sources_considered": [],
            "reason": "EVENT_NOT_FOUND_IN_AUTHORIZED_SOURCE",
        }],
    }
    submission = {
        "schema_version": "enterprise-round5-custodian-submission.v1",
        "authorization_receipt_id": projection["authorized_source_identity"]["authorization_receipt_id"],
        "custodian_id": projection["custodian_id"],
        "projection_id": projection["projection_id"],
        "acquisition_result": result,
        "observation_receipt_bindings": [],
    }
    validated = round5.validate_custodian_submission(submission, projection=projection)
    assert validated["valid"], validated["findings"]
    assert result["observations"][0]["status"] == "UNKNOWN"
