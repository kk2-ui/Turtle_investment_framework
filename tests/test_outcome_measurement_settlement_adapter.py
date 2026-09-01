from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sqlite3

import pytest

from scripts import judgment_historical_training as history
from scripts import judgment_pit_forecast as pit
from scripts import judgment_pit_forecast_control_plane as control
from scripts import judgment_selection_discovery as discovery
from scripts import judgment_v5_control_plane as v5_control
from scripts import outcome_measurement_acquisition as acquisition
from scripts import outcome_measurement_settlement_adapter as adapter
from tests.test_judgment_pit_forecast import H1_REF, _forecast, _outcome_measurement_contract, _v3_forecast
from tests.test_judgment_selection_discovery import _stage0_static_package
from tests.test_judgment_training_decision_contract import _contract


def _retro_h1() -> tuple[dict, dict]:
    """Create a pre-2014 synthetic H1 carrier for a local FY2014 outcome PDF."""
    package = _stage0_static_package()
    package["cohort_id"] = "COHORT:SYNTHETIC:20140630"
    package["selection_as_of"] = "2014-06-30T23:59:59+08:00"
    package["cohort_eligibility_as_of"] = package["selection_as_of"]
    periods: dict[str, str] = {}
    published: dict[str, str] = {}
    for member in package["members"]:
        for group in ("industry_business_evidence", "control_group_evidence"):
            for evidence in member[group]:
                evidence["published_at"] = "2014-03-30"
                published[evidence["source_id"]] = evidence["published_at"]
        for index, repetition in enumerate(member["d2_field_availability"]["repetitions"]):
            period_end = f"{2011 + index}-12-31"
            repetition["period_end"] = period_end
            for evidence in repetition["evidence"]:
                evidence["published_at"] = f"{2012 + index}-03-30"
                periods[evidence["source_id"]] = period_end
                published[evidence["source_id"]] = evidence["published_at"]
        for index, annual in enumerate(member["annual_d3_d4_availability"]):
            period_end = f"{2009 + index}-12-31"
            annual["period_end"] = period_end
            for evidence in annual["evidence"]:
                evidence["published_at"] = f"{2010 + index}-03-30"
                periods[evidence["source_id"]] = period_end
                published[evidence["source_id"]] = evidence["published_at"]

    focal = package["members"][0]
    original_issuer = focal["issuer_id"]
    focal.update({
        "company_id": "CN:600660",
        "issuer_id": "ISSUER:CN:600660",
        "responsibility_unit_id": "UNIT:600660",
        "control_group_id": "CONTROL:CN:600660",
    })
    focal["boundary"]["responsibility_unit_id"] = focal["responsibility_unit_id"]
    for group in ("industry_business_evidence", "control_group_evidence"):
        for evidence in focal[group]:
            evidence["issuer_id"] = focal["issuer_id"]
            evidence["responsibility_unit_id"] = focal["responsibility_unit_id"]
            if "observed_control_group_id" in evidence:
                evidence["observed_control_group_id"] = focal["control_group_id"]
    for repetition in focal["d2_field_availability"]["repetitions"]:
        for evidence in repetition["evidence"]:
            evidence["issuer_id"] = focal["issuer_id"]
            evidence["responsibility_unit_id"] = focal["responsibility_unit_id"]
    for annual in focal["annual_d3_d4_availability"]:
        for evidence in annual["evidence"]:
            evidence["issuer_id"] = focal["issuer_id"]
            evidence["responsibility_unit_id"] = focal["responsibility_unit_id"]
    package["universe"]["listed_company_ids"][0] = focal["company_id"]

    for member in package["members"]:
        for group in ("industry_business_evidence", "control_group_evidence"):
            for evidence in member[group]:
                published[evidence["source_id"]] = evidence["published_at"]
        for repetition in member["d2_field_availability"]["repetitions"]:
            for evidence in repetition["evidence"]:
                published[evidence["source_id"]] = evidence["published_at"]
                periods[evidence["source_id"]] = repetition["period_end"]
        for annual in member["annual_d3_d4_availability"]:
            for evidence in annual["evidence"]:
                published[evidence["source_id"]] = evidence["published_at"]
                periods[evidence["source_id"]] = annual["period_end"]
    for source in package["static_pdf_sources"]:
        source["published_at"] = published.get(source["source_id"], "2014-03-30")
        source["period_end"] = periods.get(source["source_id"], "2013-12-31")
        if source["issuer_id"] == original_issuer:
            source["issuer_id"] = focal["issuer_id"]
            source["responsibility_unit_id"] = focal["responsibility_unit_id"]
    assert discovery.validate_stage0_static_source_package(package)["state"] == discovery.STAGE0_FEASIBILITY_REVIEWABLE
    projection = history.project_stage0_h1_to_universe_and_carrier_seed(package, h1_receipt_ref=H1_REF)
    assert projection["valid"], projection["findings"]
    return package, projection["universe_snapshot"]


def _contract_for_adapter(forecast: dict, decision_contract: dict) -> dict:
    contract = _outcome_measurement_contract(forecast, decision_contract)
    contract["measurement_contract_id"] = "OMC:CN600660:ADAPTER:V1"
    for cell in contract["cells"]:
        cell["unit"] = "RMB"
        cell["source_field_id"] = f"UNSUPPORTED:{cell['measurement_id']}"
        cell["metric_definition"] = cell["source_field_id"]
        cell["mismatch_rules"] = ["ACCOUNTING_SCOPE_MISMATCH_PARENT_FIELD_CANNOT_SETTLE_CONSOLIDATED_CONTRACT"]
        if cell["measurement_kind"] == "ORDINAL_THRESHOLD":
            cell["measurement_formula"] = {
                "formula_kind": "DIRECT_NUMERIC", "value_field_id": cell["source_field_id"],
            }
            cell["lower_threshold"] = 10_000_000_000.0
            cell["upper_threshold"] = 14_000_000_000.0
    for cell in contract["cells"]:
        cell["outcome_period_end"] = {
            "ONE_YEAR": "2014-12-31", "THREE_YEAR": "2015-12-31", "FIVE_YEAR": "2016-12-31",
        }[cell["window_id"]]
    observed = next(
        cell for cell in contract["cells"]
        if cell["dimension_id"] == "NORMAL_EARNINGS" and cell["window_id"] == "ONE_YEAR"
    )
    observed.update({
        "source_field_id": "CONSOLIDATED_REVENUE_RMB",
        "metric_definition": "Consolidated annual operating revenue in RMB.",
        "measurement_formula": {"formula_kind": "DIRECT_NUMERIC", "value_field_id": "CONSOLIDATED_REVENUE_RMB"},
    })
    mismatch = next(
        cell for cell in contract["cells"]
        if cell["dimension_id"] == "ROIC_OR_OPERATING_MARGIN" and cell["window_id"] == "ONE_YEAR"
    )
    mismatch.update({
        "source_field_id": "PARENT_REVENUE_RMB",
        "metric_definition": "Parent annual operating revenue, deliberately incompatible with the consolidated boundary.",
        "measurement_formula": {"formula_kind": "DIRECT_NUMERIC", "value_field_id": "PARENT_REVENUE_RMB"},
    })
    return contract


def _conn_with_authorized_forecast() -> tuple[sqlite3.Connection, dict, dict, dict]:
    h1, universe = _retro_h1()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    control.initialize(conn)
    v5_control.initialize(conn)
    assert v5_control.register_h1_static_cohort_receipt(conn, {
        "receipt_id": H1_REF["receipt_id"], "receipt_version": H1_REF["receipt_version"],
        "recorded_at": "2014-07-01T00:00:00+00:00", "stage0_static_package": h1,
    })["registered"]
    v2 = _forecast(
        universe, h1, "CN:600660", forecast_id="FORECAST:CN600660:ADAPTER:V2",
        decision_contract_ref={"contract_id": "DC:CN600660:ADAPTER:V1", "contract_version": 1},
    )
    decision = _contract(v2)
    decision["contract_id"] = "DC:CN600660:ADAPTER:V1"
    contract = _contract_for_adapter(v2, decision)
    control.register_training_decision_contract(conn, decision, frozen_at="2014-07-02T00:00:00+00:00")
    control.register_forecast_outcome_measurement_contract(conn, contract, frozen_at="2014-07-03T00:00:00+00:00")
    forecast = _v3_forecast(v2, contract)
    control.register_company_state_forecast(
        conn, forecast, universe_snapshot=universe, stage0_package=h1, frozen_at="2014-07-04T00:00:00+00:00",
    )
    access = {
        "schema_version": pit.OUTCOME_ACCESS_SCHEMA_VERSION_V2,
        "authorization_id": "OUTCOME-ACCESS:CN600660:ADAPTER:V1",
        "forecast_id": forecast["forecast_id"],
        "company_id": forecast["company_id"],
        "cutoff_at": forecast["cutoff_at"],
        "custodian_id": decision["roles"]["outcome_custodian_id"],
        "authorized_at": "2016-04-01T00:00:00+00:00",
        "outcome_windows": list(pit.FORECAST_WINDOWS),
        "outcome_measurement_contract_ref": deepcopy(forecast["outcome_measurement_contract_ref"]),
        "object_class": "FORECAST_OUTCOME_ACCESS_AUTHORIZATION",
        "claim_class": "CUSTODIAN_ONLY_OUTCOME_ACQUISITION",
        "allowed_outputs": list(pit.OUTCOME_ACCESS_ALLOWED_OUTPUTS),
    }
    assert control.authorize_forecast_outcome_access(conn, access)["authorized"]
    return conn, forecast, contract, access


def _synthetic_inventory(contract: dict, tmp_path: Path) -> tuple[dict, callable]:
    pdf = tmp_path / "registered-official.pdf"
    pdf.write_bytes(b"%PDF-1.7 synthetic official annual report")
    inventory = {
        "schema_version": acquisition.INVENTORY_SCHEMA_VERSION,
        "inventory_id": "INV:CN600660:ADAPTER:V1",
        "measurement_contract_ref": {
            "measurement_contract_id": contract["measurement_contract_id"],
            "measurement_contract_version": contract["measurement_contract_version"],
        },
        "custodian_id": contract["custodian_id"],
        "registered_at": "2016-04-02T00:00:00+00:00",
        "documents": [{
            "source_id": "SSE:600660:ANN:20150217:600660_2014_n",
            "source_url": "https://static.sse.com.cn/disclosure/listedinfo/announcement/c/2015-02-16/600660_2014_n.pdf",
            "local_pdf_path": str(pdf),
            "issuer_id": contract["issuer_id"],
            "responsibility_boundary": contract["cells"][0]["responsibility_boundary"],
            "report_period_end": "2014-12-31",
            "official_source_type": "OFFICIAL_ANNUAL_REPORT",
            "report_scope": "ISSUER_FILING",
            "currency": "RMB",
            "revision_policy": "ORIGINAL_VINTAGE",
            "consolidation_or_restatement_note": "registered original annual report",
            "availability_precision": "DATE_ONLY",
            "source_available_at": None,
            "source_available_date": "2015-02-17",
        }],
        "object_class": acquisition.INVENTORY_OBJECT_CLASS,
        "claim_class": acquisition.INVENTORY_CLAIM_CLASS,
        "allowed_outputs": ["FORECAST_OUTCOME_ACQUISITION_ONLY"],
    }

    def pages(_: Path) -> list[str]:
        return [
            "合并利润表\n单位：元\n其中：营业收入 12,928,181,657 11,501,209,769",
            "母公司利润表\n单位：元\n一、营业收入 4,356,833,675 3,900,191,607",
        ]

    return inventory, pages


def _acquired_result(contract: dict, inventory: dict, page_reader) -> dict:
    return acquisition.acquire_outcome_measurements(contract, inventory, page_reader=page_reader)


def test_adapter_requires_stored_access_before_reading_acquisition_result(monkeypatch: pytest.MonkeyPatch) -> None:
    conn, _forecast_payload, _contract, _access = _conn_with_authorized_forecast()
    calls: list[dict] = []

    def should_not_run(result: dict) -> dict:
        calls.append(result)
        raise AssertionError("acquisition result must remain unread without stored authorization")

    monkeypatch.setattr(adapter.acquisition, "validate_acquisition_result", should_not_run)
    with pytest.raises(adapter.OutcomeMeasurementSettlementAdapterError, match="outcome_access_authorization_not_found"):
        adapter.register_acquisition_result(
            conn,
            outcome_access_authorization_id="OUTCOME-ACCESS:UNKNOWN",
            acquisition_result={"contains": "realised content"},
            observed_at="2016-04-02T00:00:00+00:00",
            settlement_id="SETTLEMENT:CN600660:ADAPTER:UNAUTHORIZED",
            settled_at="2016-04-03T00:00:00+00:00",
        )
    assert calls == []
    conn.close()


def test_adapter_settles_observed_field_without_turning_unknown_fields_into_zero(tmp_path: Path) -> None:
    conn, _forecast_payload, contract, access = _conn_with_authorized_forecast()
    inventory, reader = _synthetic_inventory(contract, tmp_path)
    result = _acquired_result(contract, inventory, reader)
    settled = adapter.register_acquisition_result(
        conn,
        outcome_access_authorization_id=access["authorization_id"],
        acquisition_result=result,
        observed_at="2016-04-02T00:00:00+00:00",
        settlement_id="SETTLEMENT:CN600660:ADAPTER:OBSERVED",
        settled_at="2016-04-03T00:00:00+00:00",
    )
    statuses = {item["measurement_id"]: item["status"] for item in settled["field_statuses"]}
    assert statuses[next(cell["measurement_id"] for cell in contract["cells"] if cell["source_field_id"] == "CONSOLIDATED_REVENUE_RMB")] == "OBSERVED"
    assert any(status == "UNKNOWN" for status in statuses.values())
    assert settled["coverage"]["observed_scored_cells"] == 1
    assert conn.execute(f"SELECT COUNT(*) FROM {control.OUTCOME_OBSERVATION_TABLE}").fetchone()[0] == 2
    conn.close()


def test_adapter_keeps_a_source_backed_mismatch_from_revoking_observed_neighbor(tmp_path: Path) -> None:
    conn, _forecast_payload, contract, access = _conn_with_authorized_forecast()
    inventory, reader = _synthetic_inventory(contract, tmp_path)
    result = _acquired_result(contract, inventory, reader)
    settled = adapter.register_acquisition_result(
        conn,
        outcome_access_authorization_id=access["authorization_id"],
        acquisition_result=result,
        observed_at="2016-04-02T00:00:00+00:00",
        settlement_id="SETTLEMENT:CN600660:ADAPTER:MIXED",
        settled_at="2016-04-03T00:00:00+00:00",
    )
    statuses = {item["measurement_id"]: item["status"] for item in settled["field_statuses"]}
    observed = next(cell["measurement_id"] for cell in contract["cells"] if cell["source_field_id"] == "CONSOLIDATED_REVENUE_RMB")
    mismatch = next(cell["measurement_id"] for cell in contract["cells"] if cell["source_field_id"] == "PARENT_REVENUE_RMB")
    assert statuses[observed] == "OBSERVED"
    assert statuses[mismatch] == "MEASUREMENT_MISMATCH"
    assert settled["coverage"]["observed_scored_cells"] == 1
    conn.close()


def _r60_fy2014_pdf() -> Path | None:
    for parent in Path(__file__).resolve().parents:
        if parent.name == "analy":
            candidate = parent / "worktrees" / "Turtle_investment_framework" / "docs-r60-fuyao-us-plant-teaching" / "output" / "research" / "r60_fuyao_us_plant_teaching" / "source_package" / "pdf" / "0003_SSE_600660_ANN_20150217_600660_2014_n.pdf"
            return candidate if candidate.is_file() else None
    return None


def test_real_registered_sse_pdf_reaches_existing_mechanical_settlement() -> None:
    pdf = _r60_fy2014_pdf()
    if pdf is None:
        pytest.skip("registered R60 local SSE FY2014 PDF is unavailable in this checkout")
    conn, _forecast_payload, contract, access = _conn_with_authorized_forecast()
    inventory, _reader = _synthetic_inventory(contract, pdf.parent)
    inventory["documents"][0]["local_pdf_path"] = str(pdf)
    result = acquisition.acquire_outcome_measurements(contract, inventory)
    settled = adapter.register_acquisition_result(
        conn,
        outcome_access_authorization_id=access["authorization_id"],
        acquisition_result=result,
        observed_at="2016-04-02T00:00:00+00:00",
        settlement_id="SETTLEMENT:CN600660:ADAPTER:REAL-SSE",
        settled_at="2016-04-03T00:00:00+00:00",
    )
    assert settled["coverage"]["observed_scored_cells"] == 1
    observation = conn.execute(f"SELECT payload_json FROM {control.OUTCOME_OBSERVATION_TABLE} LIMIT 1").fetchone()
    assert observation is not None
    assert "SSE:600660:ANN:20150217:600660_2014_n" in observation[0]
    assert "PDF p.54" in observation[0]
    conn.close()
