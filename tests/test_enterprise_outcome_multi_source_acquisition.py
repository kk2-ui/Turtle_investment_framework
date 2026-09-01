from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import enterprise_judgment_real_mechanism_training as training
from scripts import judgment_selection_candidate as v4
from scripts import outcome_measurement_acquisition as acquisition
from scripts import working_capital_model


COMPANY_ID = "CN:SYNTHETIC-MULTI"
ISSUER_ID = "ISSUER:" + COMPANY_ID
AUTHORIZATION_ID = "AUTH:ENTERPRISE:SYNTHETIC-MULTI:V1"
SOURCE_2019 = "CNINFO:SYNTHETIC:FY2019"
SOURCE_2020 = "CNINFO:SYNTHETIC:FY2020"


def _flow_clock(year: int) -> dict:
    return {
        "clock_kind": "FLOW_PERIOD",
        "flow_period": {
            "period_start": f"{year}-01-01",
            "period_end": f"{year}-12-31",
            "fiscal_period": f"FY{year}",
        },
    }


def _balance_clock(year: int) -> dict:
    return {
        "clock_kind": "BALANCE_AS_OF",
        "balance_as_of": {"as_of": f"{year}-12-31", "fiscal_period": f"FY{year}"},
    }


def _raw(
    name: str,
    role: str,
    *,
    source_id: str,
    year: int,
    balance: bool = False,
    unit: str = "RMB",
) -> dict:
    clock = _balance_clock(year) if balance else _flow_clock(year)
    return {
        "field_id": f"FIELD:SYNTHETIC:FY{year}:{name}",
        "role": role,
        "unit": unit,
        "measurement_clock": clock,
        "locator": {
            "table_or_note": f"official synthetic {name} table",
            "line_item": name,
            "period_column": f"FY{year}",
        },
        "source_id": source_id,
    }


def _cell(
    name: str,
    *,
    year: int,
    layer: str,
    component_role: str,
    component_id: str,
    raws: list[dict],
    operator: str,
    coefficients: list[str] | None = None,
    output_unit: str = "RMB",
) -> dict:
    coefficients = coefficients or ["1"] * len(raws)
    cell_id = f"CELL:SYNTHETIC:{year}:{name}"
    return {
        "cell_id": cell_id,
        "thread_id": "THREAD:SYNTHETIC:MULTI-SOURCE",
        "layer": layer,
        "outcome_period": {
            "period_start": f"{year}-01-01",
            "period_end": f"{year}-12-31",
            "fiscal_period": f"FY{year}",
        },
        "measurement_clock": _flow_clock(year),
        "responsibility_boundary": {
            "responsibility_unit_id": f"RU:{component_id}",
            "perimeter_id": f"PERIMETER:{component_id}",
            "arena_id": "ARENA:SYNTHETIC:CEMENT",
            "scope_requirement": "same named component and official-report perimeter",
            "component_role": component_role,
            "component_id": component_id,
        },
        "field_identity": {
            "outcome_field_id": f"FIELD:SYNTHETIC:DERIVED:{year}:{name}",
            "baseline_field_id": "NOT_APPLICABLE",
            "statement_scope": "COMPONENT_BOUND_OFFICIAL_DISCLOSURE",
            "table_or_note": "derived from frozen raw official fields",
            "line_item": name,
            "field_kind": "DETERMINISTIC_COMPONENT_BRIDGE",
        },
        "unit": {
            "kind": output_unit,
            "currency": "RMB" if output_unit == "RMB" else "NOT_APPLICABLE",
            "scale": "ONE",
        },
        "raw_input_fields": raws,
        "formula": {
            "operator": operator,
            "input_field_ids": [raw["field_id"] for raw in raws],
            "expression": f"frozen deterministic {operator} over ordered raw inputs",
            "unit_conversions": [
                {
                    "field_id": raw["field_id"],
                    "from_unit": raw["unit"],
                    "to_unit": output_unit,
                    "scale": "1",
                }
                for raw in raws
            ],
            "input_coefficients": [
                {"field_id": raw["field_id"], "coefficient": coefficient}
                for raw, coefficient in zip(raws, coefficients, strict=True)
            ],
            "zero_baseline_rule": "RETURN_MEASUREMENT_MISMATCH",
        },
        "label_rule": {
            "type": "ABSOLUTE_CHANGE_BAND",
            "decrease_lte": -0.01,
            "increase_gte": 0.01,
            "ordered_labels": [
                "MEASUREMENT_MISMATCH", "OBSERVED_DECREASE", "OBSERVED_STABLE",
                "OBSERVED_INCREASE", "UNKNOWN",
            ],
        },
        "conflict_rule": {
            "multiple_values": "MEASUREMENT_MISMATCH",
            "boundary_conflict": "MEASUREMENT_MISMATCH",
            "period_conflict": "MEASUREMENT_MISMATCH",
        },
        "unknown_rule": {
            "conditions": ["one or more frozen raw fields are not disclosed"],
            "label": "UNKNOWN",
        },
        "mismatch_rule": {
            "conditions": ["a frozen raw field has a different unit, period, source, or component"],
            "label": "MEASUREMENT_MISMATCH",
            "propagation": "LOCAL_ONLY",
            "dependent_cell_ids": [],
        },
        "allowed_source_types": ["OFFICIAL_AUDITED_ANNUAL_REPORT"],
        "prohibited_inference": "Do not replace an unavailable component with zero or a consolidated sibling.",
    }


def _source(source_id: str, year: int, announcement: str) -> dict:
    return {
        "source_id": source_id,
        "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
        "official_url": f"https://static.cninfo.com.cn/finalpage/{announcement}/120000{year}.PDF",
        "published_after_cutoff": True,
        "access_state": "SEALED_UNTIL_PREOUTCOME_COMMIT",
        "custodian_access": "OUTCOME_ONLY",
        "authorization_receipt_id": AUTHORIZATION_ID,
        "issuer_id": ISSUER_ID,
        "report_period_end": f"{year}-12-31",
        "availability_precision": "DATE_ONLY",
        "source_available_at": None,
        "source_available_date": f"{year + 1}-04-30",
    }


def _contract_and_values() -> tuple[dict, dict[str, tuple[float, str, str]]]:
    values: dict[str, tuple[float, str, str]] = {}

    def valued(raw: dict, value: float) -> dict:
        values[raw["field_id"]] = (value, raw["unit"], raw["source_id"])
        return raw

    owner_cash_raws = [
        valued(_raw("OCF", "OPERATING_CASH_FLOW", source_id=SOURCE_2019, year=2019), 100),
        valued(_raw("MAINTENANCE_CAPEX", "MAINTENANCE_CAPEX", source_id=SOURCE_2019, year=2019), 20),
        valued(_raw("NONCORE_ADJUSTMENT", "OWNER_CASH_ADJUSTMENT", source_id=SOURCE_2019, year=2019), -10),
    ]
    noncore_raws = [
        valued(_raw("REAL_ESTATE_OCF", "OCF_RECONCILIATION_ADJUSTMENT", source_id=SOURCE_2019, year=2019), 10),
    ]
    stock_delta_raws = [
        valued(_raw("OPENING_STOCK", "OPENING_STOCK", source_id=SOURCE_2020, year=2019, balance=True), 20),
        valued(_raw("CLOSING_STOCK", "CLOSING_STOCK", source_id=SOURCE_2020, year=2020, balance=True), 25),
    ]
    reconciliation_raws = [
        valued(_raw("CORE_COMPONENT", "RECONCILIATION_COMPONENT", source_id=SOURCE_2019, year=2019), 70),
        valued(_raw("NONCORE_COMPONENT", "RECONCILIATION_COMPONENT", source_id=SOURCE_2019, year=2019), 10),
        valued(_raw("CONSOLIDATED_TOTAL", "RECONCILIATION_TOTAL", source_id=SOURCE_2019, year=2019), 80),
    ]
    return_raws = [
        valued(_raw("COHORT_CASH_RETURN", "CASH_RETURN_NUMERATOR", source_id=SOURCE_2020, year=2020), 15),
        valued(_raw("COHORT_INVESTED_CAPITAL", "INVESTED_CAPITAL_DENOMINATOR", source_id=SOURCE_2020, year=2020, balance=True), 100),
    ]
    commitment_raws = [
        valued(_raw("PROJECT_COMMITMENT", "PROJECT_COMMITMENT", source_id=SOURCE_2020, year=2020), 120),
        valued(_raw("PROJECT_REMAINING", "PROJECT_REMAINING_COMMITMENT", source_id=SOURCE_2020, year=2020), 20),
    ]
    d3_raws = [
        valued(_raw("REVENUE", "OPERATING_REVENUE", source_id=SOURCE_2020, year=2020), 100),
        valued(_raw("COST", "OPERATING_COST", source_id=SOURCE_2020, year=2020), 60),
        valued(_raw("TAX", "TAXES_AND_SURCHARGES", source_id=SOURCE_2020, year=2020), 5),
        valued(_raw("SELLING", "SELLING_EXPENSE", source_id=SOURCE_2020, year=2020), 5),
        valued(_raw("ADMIN", "ADMINISTRATIVE_EXPENSE", source_id=SOURCE_2020, year=2020), 5),
    ]
    ocf_raw = valued(_raw("OCF_V4", "OPERATING_CASH_FLOW", source_id=SOURCE_2020, year=2020), 30)
    asset_cash_raw = valued(_raw("LONG_ASSET_CASH", "CASH_LONG_LIVED_ASSET_ACQUISITION", source_id=SOURCE_2020, year=2020), 10)
    opening_raws = [
        valued(_raw("OPEN_AR", "OPENING_ACCOUNTS_RECEIVABLE", source_id=SOURCE_2020, year=2019, balance=True), 10),
        valued(_raw("OPEN_PREPAY", "OPENING_PREPAYMENTS", source_id=SOURCE_2020, year=2019, balance=True), 2),
        valued(_raw("OPEN_INV", "OPENING_INVENTORY", source_id=SOURCE_2020, year=2019, balance=True), 8),
        valued(_raw("OPEN_AP", "OPENING_ACCOUNTS_PAYABLE", source_id=SOURCE_2020, year=2019, balance=True), 5),
        valued(_raw("OPEN_ADV", "OPENING_CUSTOMER_ADVANCES", source_id=SOURCE_2020, year=2019, balance=True), 1),
    ]
    ending_raws = [
        valued(_raw("END_AR", "ENDING_ACCOUNTS_RECEIVABLE", source_id=SOURCE_2020, year=2020, balance=True), 12),
        valued(_raw("END_PREPAY", "ENDING_PREPAYMENTS", source_id=SOURCE_2020, year=2020, balance=True), 3),
        valued(_raw("END_INV", "ENDING_INVENTORY", source_id=SOURCE_2020, year=2020, balance=True), 9),
        valued(_raw("END_AP", "ENDING_ACCOUNTS_PAYABLE", source_id=SOURCE_2020, year=2020, balance=True), 6),
        valued(_raw("END_ADV", "ENDING_CUSTOMER_ADVANCES", source_id=SOURCE_2020, year=2020, balance=True), 1),
    ]

    cells = [
        _cell("OWNER_CASH", year=2019, layer="CASH", component_role="MATURE_CORE", component_id="CORE",
              raws=owner_cash_raws, operator="OWNER_CASH"),
        _cell("REAL_ESTATE_OCF", year=2019, layer="CASH", component_role="NON_CORE_REAL_ESTATE", component_id="REAL_ESTATE",
              raws=noncore_raws, operator="SUM"),
        _cell("OCF_RECONCILIATION", year=2019, layer="CASH", component_role="MATURE_CORE", component_id="CORE",
              raws=reconciliation_raws, operator="COMPONENT_TO_TOTAL_RECONCILIATION"),
        _cell("STOCK_DELTA", year=2020, layer="WORKING_CAPITAL", component_role="MATURE_CORE", component_id="CORE",
              raws=stock_delta_raws, operator="SIGNED_STOCK_DELTA"),
        _cell("COHORT_RETURN", year=2020, layer="CAPITAL_BURDEN", component_role="NAMED_GROWTH_COHORT", component_id="COHORT:WEST",
              raws=return_raws, operator="INVESTED_CAPITAL_RETURN", output_unit="RATIO"),
        _cell("COHORT_COMMITMENT", year=2020, layer="CAPITAL_BURDEN", component_role="NAMED_GROWTH_COHORT", component_id="COHORT:WEST",
              raws=commitment_raws, operator="SUM", coefficients=["1", "-1"]),
        _cell("D3", year=2020, layer="UNIT_COST", component_role="MATURE_CORE", component_id="CORE",
              raws=d3_raws, operator="SUM", coefficients=["1", "-1", "-1", "-1", "-1"]),
        _cell("OCF_V4", year=2020, layer="CASH", component_role="MATURE_CORE", component_id="CORE",
              raws=[ocf_raw], operator="RAW_VALUE"),
        _cell("LONG_ASSET_CASH", year=2020, layer="CAPITAL_BURDEN", component_role="MATURE_CORE", component_id="CORE",
              raws=[asset_cash_raw], operator="RAW_VALUE"),
        _cell("OPENING_NWC", year=2020, layer="WORKING_CAPITAL", component_role="MATURE_CORE", component_id="CORE",
              raws=opening_raws, operator="SUM", coefficients=["1", "1", "1", "-1", "-1"]),
        _cell("ENDING_NWC", year=2020, layer="WORKING_CAPITAL", component_role="MATURE_CORE", component_id="CORE",
              raws=ending_raws, operator="SUM", coefficients=["1", "1", "1", "-1", "-1"]),
    ]
    contract = {
        "schema_version": training.CONTRACT_SCHEMA_VERSION_V3,
        "contract_set_id": "OMC:SYNTHETIC:MULTI:V1",
        "package_ref": "PACKAGE:SYNTHETIC:MULTI:V1",
        "company_id": COMPANY_ID,
        "cutoff_at": "2018-12-31T00:00:00+08:00",
        "outcome_window": {
            "period_start": "2019-01-01T00:00:00+08:00",
            "period_end": "2020-12-31T23:59:59+08:00",
            "fiscal_period": "FY2019-FY2020",
            "settlement_due_at": "2021-06-30T00:00:00+08:00",
        },
        "source_accesses": [
            _source(SOURCE_2019, 2019, "2020-04-30"),
            _source(SOURCE_2020, 2020, "2021-04-30"),
        ],
        "atomic_cells": cells,
        "thread_combination_rules": [{
            "rule_id": "COMBINE:SYNTHETIC:MULTI",
            "thread_id": "THREAD:SYNTHETIC:MULTI-SOURCE",
            "input_cell_ids": [cell["cell_id"] for cell in cells],
            "evaluation_order": [cell["cell_id"] for cell in cells],
            "rule": "Preserve each component and period before any cross-component reconciliation.",
            "conflict_rule": "A missing or mismatched raw field remains local to its cell.",
            "authorization": "TEACHING_ONLY_NO_CAUSAL_UPGRADE",
        }],
        "rights": {
            "directional_learning": "NOT_AUTHORIZED", "enterprise_learning": "NOT_AUTHORIZED",
            "comparative": "NOT_AUTHORIZED", "cjo": "NOT_AUTHORIZED", "valuation": "NOT_AUTHORIZED",
            "report": "NOT_AUTHORIZED", "investment": "NOT_AUTHORIZED",
        },
        "allowed_outputs": ["OUTCOME_CUSTODY_REQUEST", "RESEARCH_AGENDA"],
        "freeze_state": "PRE_OUTCOME_FROZEN",
        "contract_frozen_at": "2019-01-01T00:00:00+08:00",
        "clock_policy": "CUT_OFF_CLOCK_SEPARATE_FROM_MEASUREMENT_CLOCK",
    }
    return contract, values


def _custody(
    tmp_path: Path,
    *,
    omit_roles: set[str] | None = None,
    mismatch_roles: set[str] | None = None,
    conversions_by_role: dict[str, tuple[str, str, str]] | None = None,
) -> tuple[dict, dict, dict, callable]:
    contract, values = _contract_and_values()
    omit_roles = omit_roles or set()
    mismatch_roles = mismatch_roles or set()
    conversions_by_role = conversions_by_role or {}
    for cell in contract["atomic_cells"]:
        conversion_by_field = {
            item["field_id"]: item for item in cell["formula"]["unit_conversions"]
        }
        for raw in cell["raw_input_fields"]:
            conversion = conversions_by_role.get(raw["role"])
            if conversion is None:
                continue
            from_unit, to_unit, scale = conversion
            raw["unit"] = from_unit
            conversion_item = conversion_by_field[raw["field_id"]]
            conversion_item.update(from_unit=from_unit, to_unit=to_unit, scale=scale)
            value, _, source_id = values[raw["field_id"]]
            values[raw["field_id"]] = (value, from_unit, source_id)
    role_by_field = {
        raw["field_id"]: raw["role"]
        for cell in contract["atomic_cells"] for raw in cell["raw_input_fields"]
    }
    paths: dict[str, Path] = {}
    for source_id, year in ((SOURCE_2019, 2019), (SOURCE_2020, 2020)):
        lines = []
        for field_id, (value, unit, field_source_id) in values.items():
            role = role_by_field[field_id]
            if field_source_id != source_id or role in omit_roles:
                continue
            disclosed_unit = "USD" if role in mismatch_roles else unit
            lines.append(f"{field_id} | {value} | {disclosed_unit}")
        path = tmp_path / f"synthetic-{year}.pdf"
        path.write_bytes(("%PDF-1.7\n" + "\n".join(lines)).encode("utf-8"))
        paths[source_id] = path
    authorization = {
        "schema_version": acquisition.ENTERPRISE_AUTHORIZATION_SCHEMA_VERSION,
        "authorization_receipt_id": AUTHORIZATION_ID,
        "measurement_contract_ref": {
            "measurement_contract_id": contract["contract_set_id"],
            "measurement_contract_version": 3,
        },
        "company_id": COMPANY_ID,
        "custodian_id": "CUSTODIAN:SYNTHETIC:MULTI",
        "source_ids": [SOURCE_2019, SOURCE_2020],
        "authorized": True,
        "content_read": True,
    }
    documents = []
    for source in contract["source_accesses"]:
        documents.append({
            "source_id": source["source_id"],
            "source_url": source["official_url"],
            "local_pdf_path": str(paths[source["source_id"]]),
            "issuer_id": ISSUER_ID,
            "responsibility_boundary": "FROZEN_MULTI_COMPONENT_ISSUER_FILING",
            "report_period_end": source["report_period_end"],
            "official_source_type": "OFFICIAL_ANNUAL_REPORT",
            "report_scope": "ISSUER_FILING",
            "currency": "RMB",
            "revision_policy": "ORIGINAL_VINTAGE",
            "consolidation_or_restatement_note": "synthetic unchanged-boundary official report",
            "availability_precision": source["availability_precision"],
            "source_available_at": source["source_available_at"],
            "source_available_date": source["source_available_date"],
        })
    inventory = {
        "schema_version": acquisition.INVENTORY_SCHEMA_VERSION,
        "inventory_id": "INV:SYNTHETIC:MULTI:V1",
        "measurement_contract_ref": authorization["measurement_contract_ref"],
        "custodian_id": authorization["custodian_id"],
        "registered_at": "2021-05-01T00:00:00+08:00",
        "documents": documents,
        "object_class": acquisition.INVENTORY_OBJECT_CLASS,
        "claim_class": acquisition.INVENTORY_CLAIM_CLASS,
        "allowed_outputs": ["ENTERPRISE_OUTCOME_ACQUISITION_ONLY"],
    }

    def reader(path: Path) -> list[str]:
        return [path.read_bytes().split(b"\n", 1)[1].decode("utf-8")]

    return contract, authorization, inventory, reader


def _append_fy2020_ocf_reuse(contract: dict) -> str:
    source_cell = next(
        cell for cell in contract["atomic_cells"]
        if cell["cell_id"] == "CELL:SYNTHETIC:2020:OCF_V4"
    )
    reused = _cell(
        "OCF_REUSE",
        year=2020,
        layer="CASH",
        component_role="MATURE_CORE",
        component_id="CORE",
        raws=[deepcopy(source_cell["raw_input_fields"][0])],
        operator="RAW_VALUE",
    )
    contract["atomic_cells"].append(reused)
    rule = contract["thread_combination_rules"][0]
    rule["input_cell_ids"].append(reused["cell_id"])
    rule["evaluation_order"].append(reused["cell_id"])
    return reused["cell_id"]


def test_multi_source_component_contract_constructs_and_projects_existing_consumer_inputs(
    tmp_path: Path,
) -> None:
    contract, authorization, inventory, reader = _custody(tmp_path)
    contract_validation = training.validate_outcome_measurement_contract(contract)
    assert contract_validation["valid"], contract_validation["findings"]
    inventory_validation = acquisition.validate_registered_local_pdf_inventory(
        inventory, measurement_contract=contract, outcome_access_authorization=authorization,
    )
    assert inventory_validation["valid"], inventory_validation["findings"]

    acquired = acquisition.acquire_outcome_measurements(
        contract, inventory, page_reader=reader, outcome_access_authorization=authorization,
    )
    result_validation = acquisition.validate_acquisition_result(
        acquired, measurement_contract=contract, outcome_access_authorization=authorization,
    )
    assert result_validation["valid"], result_validation["findings"]
    projection = acquisition.project_enterprise_acquisition_consumers(
        contract,
        acquired,
        outcome_access_authorization=authorization,
        v4_formula_ids={"d3_formula_id": "D3:V1", "d4_formula_id": "D4:V1"},
    )

    cells = {cell["cell_id"]: cell for cell in projection["constructed_cells"]}
    assert cells["CELL:SYNTHETIC:2019:OWNER_CASH"]["computed_value"] == 70.0
    assert cells["CELL:SYNTHETIC:2019:REAL_ESTATE_OCF"]["computed_value"] == 10.0
    assert cells["CELL:SYNTHETIC:2019:OCF_RECONCILIATION"]["computed_value"] == 0.0
    assert cells["CELL:SYNTHETIC:2020:STOCK_DELTA"]["computed_value"] == 5.0
    assert cells["CELL:SYNTHETIC:2020:COHORT_RETURN"]["computed_value"] == 0.15
    assert cells["CELL:SYNTHETIC:2020:COHORT_COMMITMENT"]["computed_value"] == 100.0
    assert cells["CELL:SYNTHETIC:2020:D3"]["computed_value"] == 25.0
    assert cells["CELL:SYNTHETIC:2020:OPENING_NWC"]["computed_value"] == 14.0
    assert cells["CELL:SYNTHETIC:2020:ENDING_NWC"]["computed_value"] == 17.0

    wc_projection = projection["working_capital_model_inputs"]
    assert wc_projection["unresolved_periods"] == []
    wc_fragment = next(
        item for item in wc_projection["period_fragments"]
        if item["component_id"] == "CORE" and item["period"]["period_end"] == "2020-12-31"
    )
    movement = wc_fragment["period"]["net_movement_observation"]
    assert movement["opening_net_stock"] == 14.0
    assert movement["closing_net_stock"] == 17.0
    assert movement["observed_cash_capital_charge"] == 3.0
    period = {
        **wc_fragment["period"],
        "owner_cash_input": {
            "basis": "REPORTED_OCF", "metric": "operating_cash_flow",
            "base_metric_amount": 30.0, "maintenance_capex": 10.0,
            "other_owner_adjustments": 0.0,
            "working_capital_application": "ALREADY_REFLECTED_IN_BASE",
            "permanent_loss_application": "INCLUDED_IN_STOCK_FLOW_CHARGE",
            "evidence_ids": movement["evidence_ids"][:2],
        },
    }
    wc_model = {
        "schema_version": working_capital_model.SCHEMA_VERSION,
        "model_id": "WCM:SYNTHETIC:MULTI",
        "company_id": COMPANY_ID,
        "basis": {
            "economic_entity": "MATURE_CORE", "operating_perimeter": "PERIMETER:CORE",
            "ordinary_share_claim_scope": "LISTED_ISSUER", "currency": "RMB", "unit": "RMB",
            "as_of": "2020-12-31",
        },
        "periods": [period],
        "valuation_treatment": {
            "reference_period_id": period["period_id"], "epv_use": "NOT_USED",
            "epv_working_capital_treatment": "NOT_APPLICABLE", "terminal_route": "NOT_USED",
            "terminal_owner_cash_source": "NOT_APPLICABLE",
            "terminal_working_capital_treatment": "NOT_APPLICABLE", "stock_release_cohort_ids": [],
        },
    }
    assert working_capital_model.validate_working_capital_model(wc_model)["state"] == "REVIEWABLE"

    v4_projection = projection["v4_inputs"]
    assert all(
        item["period_end"] != "2020-12-31"
        for item in v4_projection["unresolved_periods"]
    )
    v4_observation = next(
        item["observation"] for item in v4_projection["annual_d3_d4_raw_observations"]
        if item["component_id"] == "CORE" and item["observation"]["period_end"] == "2020-12-31"
    )
    findings, normalized, valid = v4._v4_raw_observations(
        [v4_observation],
        cutoff=datetime(2022, 1, 1, tzinfo=timezone.utc),
        boundary={"unit": "RMB", "perimeter_id": "PERIMETER:CORE"},
        issuer_id=ISSUER_ID,
        d3_formula_id="D3:V1",
        d4_formula_id="D4:V1",
        prefix="synthetic",
        minimum_periods=1,
    )
    assert valid, findings
    assert normalized["2020-12-31"] == {
        "d3_value": 25.0, "d4_value": 20.0, "reference_revenue": 100.0,
    }

    financial = projection["financial_driver_inputs"]
    assert financial["unresolved_raw_fields"] == []
    owner_cash_inputs = {
        item["raw_field_role"]: item["value"]
        for item in financial["verified_observations"]
        if item["component_id"] == "CORE"
        and item["period_end"] == "2019-12-31"
        and item["raw_field_role"] in {
            "OPERATING_CASH_FLOW", "MAINTENANCE_CAPEX", "OWNER_CASH_ADJUSTMENT",
        }
    }
    assert owner_cash_inputs == {
        "OPERATING_CASH_FLOW": 100.0,
        "MAINTENANCE_CAPEX": 20.0,
        "OWNER_CASH_ADJUSTMENT": -10.0,
    }
    assert cells["CELL:SYNTHETIC:2019:OWNER_CASH"]["computed_value"] == (
        owner_cash_inputs["OPERATING_CASH_FLOW"]
        - owner_cash_inputs["MAINTENANCE_CAPEX"]
        + owner_cash_inputs["OWNER_CASH_ADJUSTMENT"]
    )
    growth_group = next(
        item for item in financial["capital_allocation_observation_groups"]
        if item["component_id"] == "COHORT:WEST"
    )
    assert growth_group["observation_ids_by_role"]["PROJECT_COMMITMENT"]
    assert growth_group["observation_ids_by_role"]["CASH_RETURN_NUMERATOR"]
    assert set(projection["rights"].values()) == {"NOT_AUTHORIZED"}


def test_multi_source_unknown_and_mismatch_remain_local_and_never_become_zero(
    tmp_path: Path,
) -> None:
    contract, authorization, inventory, reader = _custody(
        tmp_path,
        omit_roles={"INVESTED_CAPITAL_DENOMINATOR"},
        mismatch_roles={"OCF_RECONCILIATION_ADJUSTMENT"},
    )
    acquired = acquisition.acquire_outcome_measurements(
        contract, inventory, page_reader=reader, outcome_access_authorization=authorization,
    )
    projection = acquisition.project_enterprise_acquisition_consumers(
        contract, acquired, outcome_access_authorization=authorization,
    )
    cells = {cell["cell_id"]: cell for cell in projection["constructed_cells"]}
    assert cells["CELL:SYNTHETIC:2019:OWNER_CASH"]["status"] == "OBSERVED"
    assert cells["CELL:SYNTHETIC:2019:OWNER_CASH"]["computed_value"] == 70.0
    assert cells["CELL:SYNTHETIC:2019:REAL_ESTATE_OCF"]["status"] == "MEASUREMENT_MISMATCH"
    assert "computed_value" not in cells["CELL:SYNTHETIC:2019:REAL_ESTATE_OCF"]
    assert cells["CELL:SYNTHETIC:2020:COHORT_RETURN"]["status"] == "UNKNOWN"
    assert "computed_value" not in cells["CELL:SYNTHETIC:2020:COHORT_RETURN"]

    unresolved = projection["financial_driver_inputs"]["unresolved_raw_fields"]
    by_role = {item["raw_field_role"]: item for item in unresolved}
    assert by_role["INVESTED_CAPITAL_DENOMINATOR"]["status"] == "UNKNOWN"
    assert by_role["OCF_RECONCILIATION_ADJUSTMENT"]["status"] == "MEASUREMENT_MISMATCH"
    assert "value" not in by_role["INVESTED_CAPITAL_DENOMINATOR"]
    verified_roles = {
        item["raw_field_role"] for item in projection["financial_driver_inputs"]["verified_observations"]
    }
    assert "INVESTED_CAPITAL_DENOMINATOR" not in verified_roles


def test_multi_source_availability_is_strict_while_legacy_unknown_remains_supported() -> None:
    contract, _ = _contract_and_values()
    assert training.validate_outcome_measurement_contract(contract)["valid"]

    missing_date = deepcopy(contract)
    missing_date["source_accesses"][0]["source_available_date"] = None
    findings = training.validate_outcome_measurement_contract(missing_date)["findings"]
    assert any(item.endswith("source_available_date_invalid") for item in findings)

    mixed_precision = deepcopy(contract)
    mixed_precision["source_accesses"][0]["source_available_at"] = "2020-04-30T00:00:00+08:00"
    findings = training.validate_outcome_measurement_contract(mixed_precision)["findings"]
    assert any(item.endswith("date_only_cannot_include_timestamp") for item in findings)

    pre_cutoff = deepcopy(contract)
    pre_cutoff["source_accesses"][0]["source_available_date"] = "2018-12-31"
    findings = training.validate_outcome_measurement_contract(pre_cutoff)["findings"]
    assert any(item.endswith("availability_must_follow_cutoff") for item in findings)


def test_consumer_projection_applies_non_unit_scales_to_v4_and_working_capital(
    tmp_path: Path,
) -> None:
    conversions = {
        "OPERATING_REVENUE": ("RMB_10K", "RMB", "10000"),
        **{
            role: ("RMB_10K", "RMB", "10000")
            for role in acquisition._WORKING_CAPITAL_OPENING_ROLES
            + acquisition._WORKING_CAPITAL_ENDING_ROLES
        },
    }
    contract, authorization, inventory, reader = _custody(
        tmp_path, conversions_by_role=conversions,
    )
    assert training.validate_outcome_measurement_contract(contract)["valid"]
    acquired = acquisition.acquire_outcome_measurements(
        contract, inventory, page_reader=reader, outcome_access_authorization=authorization,
    )
    projection = acquisition.project_enterprise_acquisition_consumers(
        contract,
        acquired,
        outcome_access_authorization=authorization,
        v4_formula_ids={"d3_formula_id": "D3:V1", "d4_formula_id": "D4:V1"},
    )

    cells = {item["cell_id"]: item for item in projection["constructed_cells"]}
    assert cells["CELL:SYNTHETIC:2020:D3"]["computed_value"] == 999925.0
    wc_fragment = next(
        item for item in projection["working_capital_model_inputs"]["period_fragments"]
        if item["component_id"] == "CORE" and item["period"]["period_end"] == "2020-12-31"
    )
    movement = wc_fragment["period"]["net_movement_observation"]
    assert movement["opening_net_stock"] == 140000.0
    assert movement["closing_net_stock"] == 170000.0
    assert movement["observed_cash_capital_charge"] == 30000.0

    v4_observation = next(
        item["observation"] for item in projection["v4_inputs"]["annual_d3_d4_raw_observations"]
        if item["component_id"] == "CORE" and item["observation"]["period_end"] == "2020-12-31"
    )
    assert {
        field["unit"]
        for field in [*v4_observation["d3_raw_fields"].values(), *v4_observation["d4_raw_fields"].values()]
    } == {"RMB"}
    findings, normalized, valid = v4._v4_raw_observations(
        [v4_observation],
        cutoff=datetime(2022, 1, 1, tzinfo=timezone.utc),
        boundary={"unit": "RMB", "perimeter_id": "PERIMETER:CORE"},
        issuer_id=ISSUER_ID,
        d3_formula_id="D3:V1",
        d4_formula_id="D4:V1",
        prefix="synthetic",
        minimum_periods=1,
    )
    assert valid, findings
    assert normalized["2020-12-31"] == {
        "d3_value": 999925.0, "d4_value": 20.0, "reference_revenue": 1000000.0,
    }


def test_invalid_consumer_conversion_is_rejected_before_outcome_access(tmp_path: Path) -> None:
    contract, authorization, inventory, reader = _custody(
        tmp_path,
        conversions_by_role={"OPERATING_REVENUE": ("RMB_10K", "RMB", "not-a-number")},
    )
    validation = training.validate_outcome_measurement_contract(contract)
    assert not validation["valid"]
    assert any(item.endswith("scale_must_be_positive_finite") for item in validation["findings"])
    with pytest.raises(acquisition.OutcomeMeasurementAcquisitionError, match="measurement_contract_invalid"):
        acquisition.acquire_outcome_measurements(
            contract,
            inventory,
            page_reader=reader,
            outcome_access_authorization=authorization,
        )


def test_reused_source_fact_is_deduplicated_and_conflict_is_a_mismatch(tmp_path: Path) -> None:
    contract, authorization, inventory, reader = _custody(tmp_path)
    reused_cell_id = _append_fy2020_ocf_reuse(contract)
    reused_cell = next(
        cell for cell in contract["atomic_cells"] if cell["cell_id"] == reused_cell_id
    )
    reused_cell["outcome_period"]["period_start"] = "2019-01-01"
    reused_cell["outcome_period"]["fiscal_period"] = "FY2019-FY2020"
    validation = training.validate_outcome_measurement_contract(contract)
    assert validation["valid"], validation["findings"]
    acquired = acquisition.acquire_outcome_measurements(
        contract, inventory, page_reader=reader, outcome_access_authorization=authorization,
    )
    projection = acquisition.project_enterprise_acquisition_consumers(
        contract,
        acquired,
        outcome_access_authorization=authorization,
        v4_formula_ids={"d3_formula_id": "D3:V1", "d4_formula_id": "D4:V1"},
    )
    assert any(
        item["component_id"] == "CORE" and item["observation"]["period_end"] == "2020-12-31"
        for item in projection["v4_inputs"]["annual_d3_d4_raw_observations"]
    )
    fy2020_ocf = [
        item for item in projection["financial_driver_inputs"]["verified_observations"]
        if item["component_id"] == "CORE"
        and item["period_end"] == "2020-12-31"
        and item["raw_field_role"] == "OPERATING_CASH_FLOW"
    ]
    assert len(fy2020_ocf) == 1
    observation_ids = [
        item["observation_id"]
        for item in projection["financial_driver_inputs"]["verified_observations"]
    ]
    assert len(observation_ids) == len(set(observation_ids))

    conflicting = deepcopy(acquired)
    reused_observation = next(
        item for item in conflicting["observations"] if item["measurement_id"] == reused_cell_id
    )
    reused_observation["raw_field_observations"][0]["raw_value"] = 31.0
    conflict_projection = acquisition.project_enterprise_acquisition_consumers(
        contract,
        conflicting,
        outcome_access_authorization=authorization,
        v4_formula_ids={"d3_formula_id": "D3:V1", "d4_formula_id": "D4:V1"},
    )
    unresolved = next(
        item for item in conflict_projection["v4_inputs"]["unresolved_periods"]
        if item["component_id"] == "CORE" and item["period_end"] == "2020-12-31"
    )
    assert unresolved["status"] == "MEASUREMENT_MISMATCH"
    assert "OPERATING_CASH_FLOW" in unresolved["unresolved_roles"]
    assert not any(
        item["component_id"] == "CORE" and item["observation"]["period_end"] == "2020-12-31"
        for item in conflict_projection["v4_inputs"]["annual_d3_d4_raw_observations"]
    )


def test_reviewer_duplicate_field_id_role_rebinding_is_invalid() -> None:
    contract, _ = _contract_and_values()
    d3 = next(cell for cell in contract["atomic_cells"] if cell["cell_id"].endswith(":D3"))
    ocf_v4 = next(
        cell for cell in contract["atomic_cells"] if cell["cell_id"].endswith(":OCF_V4")
    )
    rebound_field_id = ocf_v4["raw_input_fields"][0]["field_id"]
    d3["raw_input_fields"][0]["field_id"] = rebound_field_id
    d3["formula"]["input_field_ids"][0] = rebound_field_id
    d3["formula"]["unit_conversions"][0]["field_id"] = rebound_field_id
    d3["formula"]["input_coefficients"][0]["field_id"] = rebound_field_id

    validation = training.validate_outcome_measurement_contract(contract)
    assert not validation["valid"]
    assert any(
        item.endswith("raw_field_id_semantic_binding_conflict")
        for item in validation["findings"]
    )


@pytest.mark.parametrize(
    "dimension",
    [
        "source_id",
        "measurement_clock",
        "locator",
        "unit",
        "role",
        "component_role",
        "component_id",
        "responsibility_unit_id",
        "perimeter_id",
    ],
)
def test_repeated_field_id_requires_one_contract_wide_semantic_binding(
    dimension: str,
) -> None:
    contract, _ = _contract_and_values()
    reused_cell_id = _append_fy2020_ocf_reuse(contract)
    assert training.validate_outcome_measurement_contract(contract)["valid"]
    reused_cell = next(
        cell for cell in contract["atomic_cells"] if cell["cell_id"] == reused_cell_id
    )
    raw = reused_cell["raw_input_fields"][0]
    boundary = reused_cell["responsibility_boundary"]
    if dimension == "source_id":
        raw["source_id"] = SOURCE_2019
    elif dimension == "measurement_clock":
        raw["measurement_clock"] = _flow_clock(2019)
    elif dimension == "locator":
        raw["locator"]["line_item"] = "different physical line item"
    elif dimension == "unit":
        raw["unit"] = "RMB_10K"
        reused_cell["formula"]["unit_conversions"][0]["from_unit"] = "RMB_10K"
    elif dimension == "role":
        raw["role"] = "OWNER_CASH_ADJUSTMENT"
    elif dimension == "component_role":
        boundary["component_role"] = "NON_CORE_REAL_ESTATE"
    elif dimension == "component_id":
        boundary["component_id"] = "CORE:ALTERNATE"
    elif dimension == "responsibility_unit_id":
        boundary["responsibility_unit_id"] = "RU:CORE:ALTERNATE"
    elif dimension == "perimeter_id":
        boundary["perimeter_id"] = "PERIMETER:CORE:ALTERNATE"

    validation = training.validate_outcome_measurement_contract(contract)
    assert not validation["valid"]
    assert any(
        item.endswith("raw_field_id_semantic_binding_conflict")
        for item in validation["findings"]
    )


@pytest.mark.parametrize("scale", ["-1", "0", "NaN", "Infinity", "not-a-number"])
def test_multi_source_conversion_scale_must_be_positive_finite(scale: str) -> None:
    contract, _ = _contract_and_values()
    owner_cash = next(
        cell for cell in contract["atomic_cells"] if cell["cell_id"].endswith(":OWNER_CASH")
    )
    owner_cash["formula"]["unit_conversions"][1]["scale"] = scale
    validation = training.validate_outcome_measurement_contract(contract)
    assert not validation["valid"]
    assert any(item.endswith("scale_must_be_positive_finite") for item in validation["findings"])


def test_owner_cash_intrinsic_subtraction_rejects_negative_input_coefficient() -> None:
    contract, _ = _contract_and_values()
    owner_cash = next(
        cell for cell in contract["atomic_cells"] if cell["cell_id"].endswith(":OWNER_CASH")
    )
    owner_cash["formula"]["input_coefficients"][1]["coefficient"] = "-1"
    validation = training.validate_outcome_measurement_contract(contract)
    assert not validation["valid"]
    assert any(
        item.endswith("intrinsically_signed_operator_requires_positive_coefficients")
        for item in validation["findings"]
    )


@pytest.mark.parametrize(
    ("cell_suffix", "role", "wrong_coefficient"),
    [
        (":D3", "OPERATING_REVENUE", "-1"),
        (":COHORT_COMMITMENT", "PROJECT_REMAINING_COMMITMENT", "1"),
        (":OPENING_NWC", "OPENING_ACCOUNTS_PAYABLE", "1"),
        (":REAL_ESTATE_OCF", "OCF_RECONCILIATION_ADJUSTMENT", "-1"),
    ],
)
def test_sum_coefficients_must_match_canonical_raw_role(
    cell_suffix: str,
    role: str,
    wrong_coefficient: str,
) -> None:
    contract, _ = _contract_and_values()
    cell = next(
        candidate
        for candidate in contract["atomic_cells"]
        if candidate["cell_id"].endswith(cell_suffix)
    )
    role_index = next(
        index
        for index, raw in enumerate(cell["raw_input_fields"])
        if raw["role"] == role
    )
    cell["formula"]["input_coefficients"][role_index]["coefficient"] = wrong_coefficient
    validation = training.validate_outcome_measurement_contract(contract)
    assert not validation["valid"]
    assert any(
        item.endswith("coefficient_must_match_raw_role")
        for item in validation["findings"]
    )


def test_signed_sum_requires_complete_canonical_role_pattern() -> None:
    contract, _ = _contract_and_values()
    d3 = next(cell for cell in contract["atomic_cells"] if cell["cell_id"].endswith(":D3"))
    d3["raw_input_fields"].pop()
    d3["formula"]["input_field_ids"].pop()
    d3["formula"]["unit_conversions"].pop()
    d3["formula"]["input_coefficients"].pop()
    validation = training.validate_outcome_measurement_contract(contract)
    assert not validation["valid"]
    assert any(
        item.endswith("signed_sum_raw_role_pattern_invalid")
        for item in validation["findings"]
    )


def test_multi_source_event_conversion_requires_unit_scale() -> None:
    contract, _ = _contract_and_values()
    event_cell = next(
        cell
        for cell in contract["atomic_cells"]
        if cell["cell_id"].endswith(":REAL_ESTATE_OCF")
    )
    raw = event_cell["raw_input_fields"][0]
    raw.update(
        role="EVENT",
        unit="BOOLEAN_EVENT",
        measurement_clock={
            "clock_kind": "EVENT_WINDOW",
            "event_window": {
                "event_start": "2019-01-01",
                "event_end": "2019-12-31",
                "window_name": "FY2019",
            },
        },
    )
    raw["locator"]["period_column"] = "2019-01-01..2019-12-31"
    event_cell["unit"].update(
        kind="BOOLEAN_EVENT", currency="NOT_APPLICABLE", scale="ONE"
    )
    event_cell["formula"]["operator"] = "EVENT_BOOLEAN"
    event_cell["formula"]["unit_conversions"][0].update(
        from_unit="BOOLEAN_EVENT", to_unit="BOOLEAN_EVENT", scale="2"
    )
    event_cell["label_rule"].update(
        type="EVENT_PRESENCE",
        ordered_labels=[
            "MEASUREMENT_MISMATCH", "OBSERVED_YES", "OBSERVED_NO", "UNKNOWN",
        ],
    )
    validation = training.validate_outcome_measurement_contract(contract)
    assert not validation["valid"]
    assert any(item.endswith("event_scale_must_equal_one") for item in validation["findings"])


def test_multi_source_custodian_locator_must_equal_frozen_locator(
    tmp_path: Path,
) -> None:
    contract, authorization, inventory, reader = _custody(tmp_path)
    acquired = acquisition.acquire_outcome_measurements(
        contract,
        inventory,
        page_reader=reader,
        outcome_access_authorization=authorization,
    )
    tampered = deepcopy(acquired)
    source = tampered["observations"][0]["raw_field_observations"][0]["source"]
    source["custodian_locator"]["line_item"] = "different nonempty locator"

    result_validation = acquisition.validate_acquisition_result(
        tampered,
        measurement_contract=contract,
        outcome_access_authorization=authorization,
    )
    assert not result_validation["valid"]
    assert any(
        item.endswith("source_custodian_locator_must_match_frozen_raw_input")
        for item in result_validation["findings"]
    )

    field_records = [
        {"cell_id": observation["measurement_id"], **deepcopy(raw)}
        for observation in tampered["observations"]
        for raw in observation["raw_field_observations"]
    ]
    with pytest.raises(
        acquisition.OutcomeMeasurementAcquisitionError,
        match="field_record_source_custodian_locator_must_match_frozen_locator",
    ):
        acquisition.acquire_outcome_measurements(
            contract,
            inventory,
            field_records=field_records,
            outcome_access_authorization=authorization,
        )


def test_component_id_has_one_role_and_responsibility_identity() -> None:
    contract, _ = _contract_and_values()

    wrong_role = deepcopy(contract)
    wrong_role["atomic_cells"][0]["responsibility_boundary"]["component_role"] = "NON_CORE_REAL_ESTATE"
    findings = training.validate_outcome_measurement_contract(wrong_role)["findings"]
    assert any(item.endswith("component_id_identity_conflict") for item in findings)

    wrong_responsibility_unit = deepcopy(contract)
    wrong_responsibility_unit["atomic_cells"][0]["responsibility_boundary"]["responsibility_unit_id"] = "RU:OTHER"
    findings = training.validate_outcome_measurement_contract(wrong_responsibility_unit)["findings"]
    assert any(item.endswith("component_id_identity_conflict") for item in findings)

    shared_perimeter = deepcopy(contract)
    for cell in shared_perimeter["atomic_cells"]:
        if cell["responsibility_boundary"]["component_id"] == "COHORT:WEST":
            cell["responsibility_boundary"]["perimeter_id"] = "PERIMETER:CORE"
    validation = training.validate_outcome_measurement_contract(shared_perimeter)
    assert validation["valid"], validation["findings"]
