from __future__ import annotations

import sqlite3

import pytest

from scripts import enterprise_judgment_round10_appliance_v2 as round10
from scripts import enterprise_judgment_round10_appliance_v2_control as control


def test_freezes_exact_nine_field_chains_without_opening_custody() -> None:
    conn = sqlite3.connect(":memory:")
    try:
        frozen = control.freeze_preoutcome_batch(conn)
        assert frozen["stage"] == "ROUND10_PREOUTCOME_BATCH_REGISTERED"
        assert frozen["field_count"] == 9
        assert [row["company_id"] for row in frozen["field_receipts"]] == [
            "CN:002035", "CN:002035", "CN:002035",
            "CN:002508", "CN:002508", "CN:002508",
            "CN:002677", "CN:002677", "CN:002677",
        ]
        assert control.database_counts(conn) == {
            "decision": 9, "route": 9, "measurement": 9, "evidence": 9, "prediction": 9,
            "access": 0, "inventory": 0, "observation": 0, "settlement": 0,
        }
    finally:
        conn.close()


def test_contract_only_access_requests_expose_no_prediction_or_outcome() -> None:
    requests = control.build_contract_only_outcome_access_requests()
    assert len(requests) == 9
    assert len({request["authorization_id"] for request in requests}) == 9
    forbidden = {"prediction_id", "predicted_direction", "baseline", "enhanced", "numeric_value", "outcome", "price"}
    for request in requests:
        assert not forbidden.intersection(request)
        assert request["allowed_outputs"] == ["MECHANICAL_SETTLEMENT_ONLY"]
        assert request["method_transfer_rights"] == "NO_METHOD_TRANSFER_RIGHTS"


@pytest.mark.parametrize("mutation", ["prediction", "route", "source", "roster"])
def test_public_adapter_refuses_substitute_batches_before_any_write(mutation: str) -> None:
    batch = round10.build_real_preoutcome_batch()
    if mutation == "prediction":
        batch["company_packages"][0]["minimal_field_chains"][0]["prediction"]["predicted_direction"] = "DECREASE"
    elif mutation == "route":
        chain = batch["company_packages"][0]["minimal_field_chains"][0]
        chain["technical_route_identity"]["organization_id"] = "unverified-replacement"
        chain["measurement_contract"]["outcome_acquisition_route"]["organization_id"] = "unverified-replacement"
    elif mutation == "source":
        batch["company_packages"][0]["minimal_field_chains"][0]["static_evidence"]["source"]["source_id"] = "CNINFO:REPLACED"
    else:
        batch["company_packages"].reverse()
    conn = sqlite3.connect(":memory:")
    try:
        with pytest.raises(TypeError):
            control.freeze_preoutcome_batch(conn, batch=batch)  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            control.build_contract_only_outcome_access_requests(batch=batch)  # type: ignore[call-arg]
        assert control.database_counts(conn) == {
            "decision": 0, "route": 0, "measurement": 0, "evidence": 0, "prediction": 0,
            "access": 0, "inventory": 0, "observation": 0, "settlement": 0,
        }
    finally:
        conn.close()
