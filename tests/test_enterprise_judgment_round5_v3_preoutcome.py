from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path

import pytest

from scripts import enterprise_judgment_real_mechanism_training as training
from scripts import enterprise_judgment_reconstruction as reconstruction
from scripts import enterprise_judgment_training_control_plane as control
from scripts import judgment_historical_training as history
from scripts import outcome_measurement_acquisition as acquisition
from scripts import outcome_measurement_round5_adapter as round5
from scripts import outcome_measurement_settlement_adapter as settlement_adapter


ROOT = Path(__file__).resolve().parents[1]
BLOCK_DIR = ROOT / "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018"
V2_PACKAGE = BLOCK_DIR / "26_round5_preoutcome_mechanism_package.json"
V3_PACKAGE = BLOCK_DIR / "29_round5_v3_preoutcome_mechanism_package.json"
CUSTODY_PROJECTION = BLOCK_DIR / "30_round5_v3_value_free_custody_projection.json"
CONTROL_RECEIPT = BLOCK_DIR / "31_round5_v3_preoutcome_control_plane_receipt.json"
ADAPTER_RECEIPT = BLOCK_DIR / "32_round5_v3_adapter_acceptance_receipt.json"
FREEZE_AT = "2026-08-26T16:30:00+00:00"
RECEIPT_FILES = [
    "05_feedback_settlement_001.json",
    "07_feedback_settlement_002.json",
    "13_round2_continuation_feedback_settlement.json",
    "20_round3_feedback_settlement.json",
    "25_round4_contract_insufficiency_adjudication.json",
]
H1_RECEIPT = {"receipt_id": "H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1", "receipt_version": 1}


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


def _selection_validation_context() -> dict:
    h1 = _load(ROOT / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json")
    series = history.build_industry_history_series_from_h1(h1, h1_receipt_ref=H1_RECEIPT)
    assert series["valid"], series["findings"]
    source_episodes = _load("01_e0_context_episodes.json") + _load("03_enterprise_judgment_episodes.json")
    completed = [_load(RECEIPT_FILES[0]), _load(RECEIPT_FILES[1])]
    round2_chain = {
        "eligibility_register": _load("11a_round2_eligibility_register.json"),
        "selection": _load("11_round2_transition_selection.json"),
        "target_models": _load("09_round2_enterprise_system_models.json"),
        "target_episode": _load("10_round2_preoutcome_episode.json"),
        "application": _load("12_transfer_application_receipt.json"),
        "continuation_settlement": _load("13_round2_continuation_feedback_settlement.json"),
        "review": _load("14_transfer_application_independent_review.json"),
        "completion": _load("15_round2_completion_receipt.json"),
        "source_feedback_settlement": completed[0],
    }
    return {
        "h1_package": h1,
        "history_series": series["industry_history_series"],
        "source_models": _load("02_enterprise_system_models.json"),
        "source_block_episodes": source_episodes,
        "completed_feedback_settlements": completed,
        "source_feedback_settlement": completed[0],
        "round2_eligibility_register": round2_chain["eligibility_register"],
        "round2_selection": round2_chain["selection"],
        "round2_target_models": round2_chain["target_models"],
        "round2_target_episode": round2_chain["target_episode"],
        "round2_application": round2_chain["application"],
        "round2_chain": round2_chain,
        "round3_selection": _load("16_round3_method_transfer_selection.json"),
        "round3_target_models": _load("17_round3_enterprise_system_models.json"),
        "round3_target_episode": _load("18_round3_preoutcome_episode.json"),
        "round3_application": _load("19_round3_transfer_application_receipt.json"),
    }


def _register_selection_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[dict, list[dict]]:
    monkeypatch.setattr(reconstruction, "CANONICAL_REGISTRY_PATH", tmp_path / "canonical.db")
    block = _load("04_industry_learning_block.json")
    freeze = _load("04_pre_outcome_roster_freeze.json")
    receipts = [_load(name) for name in RECEIPT_FILES]
    assert control.register_roster_freeze(
        {"block": block, "roster_freeze": freeze}, registered_at="2026-08-26T16:20:00+00:00",
    )["registered"]
    validation_context = _selection_validation_context()
    for index, receipt in enumerate(receipts):
        assert control.register_selection_receipt(
            receipt,
            roster_freeze_ref={"freeze_id": freeze["freeze_id"]},
            validation_context=validation_context,
            registered_at=f"2026-08-26T16:{21 + index:02d}:00+00:00",
        )["registered"]
    return {"freeze_id": freeze["freeze_id"]}, _receipt_refs(receipts)


def _v3_package() -> dict:
    return round5.build_round5_v3_package(_load(V2_PACKAGE), frozen_at=FREEZE_AT)


def _enterprise_synthetic_custody(
    tmp_path: Path,
) -> tuple[dict, dict, dict, callable]:
    package = _v3_package()
    contract = package["outcome_measurement_contract"]
    projection = round5.build_value_free_custody_projection(package)
    source = projection["authorized_source_identity"]
    authorization = {
        "schema_version": acquisition.ENTERPRISE_AUTHORIZATION_SCHEMA_VERSION,
        "authorization_receipt_id": source["authorization_receipt_id"],
        "measurement_contract_ref": {
            "measurement_contract_id": contract["contract_set_id"],
            "measurement_contract_version": 3,
        },
        "company_id": contract["company_id"],
        "custodian_id": projection["custodian_id"],
        "source_id": source["source_id"],
        "authorized": True,
        "content_read": True,
    }
    values: dict[str, tuple[str, str]] = {}
    omitted_event = "FIELD:600802:FY2015:DIRECT_LOSS_EVENT"
    for cell in contract["atomic_cells"]:
        for index, raw in enumerate(cell["raw_input_fields"]):
            if raw["field_id"] == omitted_event:
                continue
            if raw["role"] == "EVENT":
                token = "EVENT_FALSE" if "CUSTOMER_RESPONSE" in raw["field_id"] else "EVENT_TRUE"
            else:
                token = str(1000 + index + (100 if "FY2015" in raw["field_id"] else 0))
            values.setdefault(raw["field_id"], (token, raw["unit"]))
    text = "\n".join(f"{field_id} | {token} | {unit}" for field_id, (token, unit) in values.items())
    pdf = tmp_path / "synthetic-enterprise-outcome.pdf"
    pdf.write_bytes(b"%PDF-1.7\n" + text.encode("utf-8"))
    inventory = {
        "schema_version": acquisition.INVENTORY_SCHEMA_VERSION,
        "inventory_id": "INV:CN600802:ROUND5:SYNTHETIC:V3",
        "measurement_contract_ref": authorization["measurement_contract_ref"],
        "custodian_id": authorization["custodian_id"],
        "registered_at": "2016-04-27T01:00:00+00:00",
        "documents": [{
            "source_id": source["source_id"],
            "source_url": source["official_url"],
            "local_pdf_path": str(pdf),
            "issuer_id": "ISSUER:CN:600802",
            "responsibility_boundary": "ISSUER_CONSOLIDATED:CN:600802",
            "report_period_end": "2015-12-31",
            "official_source_type": "OFFICIAL_ANNUAL_REPORT",
            "report_scope": "ISSUER_FILING",
            "currency": "RMB",
            "revision_policy": "ORIGINAL_VINTAGE",
            "consolidation_or_restatement_note": "synthetic unchanged-boundary fixture",
            "availability_precision": "DATE_ONLY",
            "source_available_at": None,
            "source_available_date": "2016-04-26",
        }],
        "object_class": acquisition.INVENTORY_OBJECT_CLASS,
        "claim_class": acquisition.INVENTORY_CLAIM_CLASS,
        "allowed_outputs": ["ENTERPRISE_OUTCOME_ACQUISITION_ONLY"],
    }

    def reader(path: Path) -> list[str]:
        return [path.read_bytes()[9:].decode("utf-8")]

    return contract, authorization, inventory, reader


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


def test_adapter_acceptance_receipt_keeps_only_v3_active_and_real_outcome_sealed() -> None:
    receipt = _load(ADAPTER_RECEIPT)
    assert set(receipt["active_artifact_refs"].values()) == {
        "29_round5_v3_preoutcome_mechanism_package.json",
        "30_round5_v3_value_free_custody_projection.json",
        "31_round5_v3_preoutcome_control_plane_receipt.json",
    }
    assert receipt["synthetic_public_preflight"]["acquisition_to_submission_to_settlement_completed"] is True
    assert receipt["synthetic_public_preflight"]["settled_cell_count"] == 14
    assert receipt["enterprise_v3_adapter"]["raw_input_receipt_count"] == 31
    assert receipt["real_outcome_state"] == {
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

    forged = _load("25_round4_contract_insufficiency_adjudication.json")
    forged["independent_review_findings"] = []
    with pytest.raises(control.TrainingControlPlaneError) as exc:
        control.register_selection_receipt(
            forged,
            roster_freeze_ref=roster_ref,
            validation_context=_selection_validation_context(),
            registered_at="2026-08-26T16:25:00+00:00",
        )
    assert exc.value.code == "selection_receipt_production_validation_failed"


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


def test_enterprise_v3_public_acquisition_submission_and_settlement_preflight(tmp_path: Path) -> None:
    contract, authorization, inventory, reader = _enterprise_synthetic_custody(tmp_path)
    result = acquisition.acquire_outcome_measurements(
        contract,
        inventory,
        page_reader=reader,
        outcome_access_authorization=authorization,
    )
    validation = acquisition.validate_acquisition_result(
        result,
        measurement_contract=contract,
        outcome_access_authorization=authorization,
    )
    assert validation["valid"], validation["findings"]
    assert len(result["observations"]) == 14
    by_cell = {item["measurement_id"]: item for item in result["observations"]}
    assert by_cell["CELL:600802:20150415:DIRECT_LOSS_EVENT"]["status"] == "UNKNOWN"
    assert by_cell["CELL:600802:20150415:CUSTOMER_RESPONSE_EVENT"]["status"] == "OBSERVED"
    price = by_cell["CELL:600802:20150415:CEMENT_REALIZED_PRICE"]
    assert len(price["raw_field_observations"]) == 4
    assert all(raw["source"]["pdf_page"] == 1 for raw in price["raw_field_observations"])

    projection = round5.build_value_free_custody_projection(_v3_package())
    submission = {
        "schema_version": "enterprise-round5-custodian-submission.v1",
        "authorization_receipt_id": authorization["authorization_receipt_id"],
        "custodian_id": projection["custodian_id"],
        "projection_id": projection["projection_id"],
        "outcome_access_authorization": authorization,
        "acquisition_result": result,
    }
    validated = round5.validate_custodian_submission(
        submission, projection=projection, measurement_contract=contract,
    )
    assert validated["valid"], validated["findings"]
    settled = round5.settle_via_public_adapter(
        measurement_contract=contract,
        outcome_access_authorization=authorization,
        acquisition_result=result,
        observed_at="2016-04-27T02:00:00+00:00",
        settlement_id="SETTLEMENT:CN600802:ROUND5:SYNTHETIC:V3",
        settled_at="2016-04-27T03:00:00+00:00",
    )
    assert settled["coverage"] == {
        "frozen_cells": 14,
        "settled_cells": 14,
        "observed_cells": 13,
        "unknown_cells": 1,
        "measurement_mismatch_cells": 0,
    }
    settled_cells = {item["cell_id"]: item for item in settled["cell_results"]}
    assert settled_cells["CELL:600802:20150415:DIRECT_LOSS_EVENT"]["label"] == "UNKNOWN"
    assert settled_cells["CELL:600802:20150415:CUSTOMER_RESPONSE_EVENT"]["label"] == "OBSERVED_NO"
    assert len(settled["raw_observation_receipts"]) == sum(
        len(cell["raw_input_fields"]) for cell in contract["atomic_cells"]
    )


@pytest.mark.parametrize("mutation", ["fake_cell", "missing_cell", "duplicate_cell", "missing_raw_input"])
def test_enterprise_submission_rejects_nonexact_cell_or_raw_input_coverage(
    tmp_path: Path, mutation: str,
) -> None:
    contract, authorization, inventory, reader = _enterprise_synthetic_custody(tmp_path)
    result = acquisition.acquire_outcome_measurements(
        contract, inventory, page_reader=reader, outcome_access_authorization=authorization,
    )
    if mutation == "fake_cell":
        fake = deepcopy(result["observations"][0])
        fake["measurement_id"] = "CELL:FAKE"
        result["observations"].append(fake)
    elif mutation == "missing_cell":
        result["observations"].pop()
    elif mutation == "duplicate_cell":
        result["observations"].append(deepcopy(result["observations"][0]))
    else:
        multi = next(item for item in result["observations"] if len(item["raw_field_observations"]) == 4)
        multi["raw_field_observations"] = multi["raw_field_observations"][:1]
    validation = acquisition.validate_acquisition_result(
        result, measurement_contract=contract, outcome_access_authorization=authorization,
    )
    assert not validation["valid"]


def test_enterprise_formula_supports_raw_value_and_frozen_conversion() -> None:
    cell = deepcopy(_v3_package()["outcome_measurement_contract"]["atomic_cells"][2])
    raw = deepcopy(cell["raw_input_fields"][0])
    cell["raw_input_fields"] = [raw]
    cell["formula"] = {
        "operator": "RAW_VALUE",
        "input_field_ids": [raw["field_id"]],
        "expression": raw["field_id"],
        "unit_conversions": [{
            "field_id": raw["field_id"], "from_unit": raw["unit"], "to_unit": raw["unit"], "scale": "0.001",
        }],
        "zero_baseline_rule": "NOT_APPLICABLE",
    }
    assert settlement_adapter.execute_enterprise_formula(cell, [{
        "field_id": raw["field_id"], "unit": raw["unit"], "raw_value": 1000.0,
    }]) == 1.0


def test_enterprise_public_settlement_keeps_acquisition_mismatch_sibling_local(tmp_path: Path) -> None:
    contract, authorization, inventory, reader = _enterprise_synthetic_custody(tmp_path)
    pdf = Path(inventory["documents"][0]["local_pdf_path"])
    lines = pdf.read_text(encoding="utf-8").splitlines()
    lines = [
        line.removesuffix("RMB") + "USD"
        if line.startswith("FIELD:600802:FY2015:SELLING_EXPENSE_RMB |") else line
        for line in lines
    ]
    pdf.write_text("\n".join(lines), encoding="utf-8")
    result = acquisition.acquire_outcome_measurements(
        contract, inventory, page_reader=reader, outcome_access_authorization=authorization,
    )
    settled = settlement_adapter.register_acquisition_result(
        measurement_contract=contract,
        outcome_access_authorization=authorization,
        acquisition_result=result,
        observed_at="2016-04-27T02:00:00+00:00",
        settlement_id="SETTLEMENT:CN600802:ROUND5:SYNTHETIC:MISMATCH",
        settled_at="2016-04-27T03:00:00+00:00",
    )
    by_cell = {item["cell_id"]: item for item in settled["cell_results"]}
    assert by_cell["CELL:600802:20150415:SELLING_EXPENSE"]["status"] == "MEASUREMENT_MISMATCH"
    assert by_cell["CELL:600802:20150415:OPERATING_CASH"]["status"] == "OBSERVED"
    assert settled["coverage"]["measurement_mismatch_cells"] == 1
