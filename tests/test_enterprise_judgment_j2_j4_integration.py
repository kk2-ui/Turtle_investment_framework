from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import sqlite3

from scripts import enterprise_judgment_comparative_projection as j4
from scripts import enterprise_judgment_forecast_projection as j3
from scripts import enterprise_judgment_mechanism as j2
from scripts import enterprise_judgment_reconstruction as j1
from tests.test_enterprise_judgment_mechanism import _bound_inputs, _thread_set


def _forecast_source(
    manifest: dict,
    thread_set_id: str,
    thread_id: str,
    *,
    source_packet_ref: dict,
    source_id: str,
    available_at: str,
) -> dict:
    return {
        "schema_version": j3.SOURCE_SCHEMA_VERSION,
        "projection_id": "J3:SYNTHETIC:J2-INTEGRATION",
        "episode_ref": {
            "episode_id": manifest["episode_id"],
            "company_id": manifest["company_id"],
            "issuer_id": manifest["issuer_id"],
            "cutoff_at": manifest["cutoff_at"],
        },
        "mechanism_thread_set_ref": {
            "thread_set_id": thread_set_id,
            "schema_version": j3.J2_SCHEMA_VERSION,
        },
        "source_packet_refs": [deepcopy(source_packet_ref)],
        "threads": [{
            "thread_id": thread_id,
            "cells": [{
                "request_id": "REQ:J2-INTEGRATION:CASH:ONE_YEAR",
                "outcome_cell_id": "CELL:CASH",
                "forecast_eligible": True,
                "forecast_dimension_id": "CASH_CONVERSION_AND_CAPEX_BURDEN",
                "window_id": "ONE_YEAR",
                "request_kind": "ORDINAL_PROBABILITY",
                "measurement_ref": {
                    "measurement_contract_id": "MC:CASH:V1",
                    "measurement_contract_version": 1,
                    "measurement_id": "MEASURE:J2-INTEGRATION:CASH:ONE_YEAR",
                },
                "evidence_refs": [{
                    "source_id": source_id,
                    "published_at": available_at[:10],
                    "available_at": available_at,
                    "field_ref": "Official cutoff-visible operating disclosure p12.",
                    "field_id": "FIELD:J2-INTEGRATION:CASH",
                }],
                "baseline_reference": "Cutoff-visible company-state baseline only.",
            }],
        }],
        "object_class": "ENTERPRISE_JUDGMENT_FORECAST_PROJECTION_SOURCE",
        "claim_class": "J2_FORECAST_ELIGIBILITY_ROUTING",
        "allowed_outputs": list(j3.ALLOWED_OUTPUTS),
    }


def test_j2_routes_forecast_and_comparative_locally_without_global_promotion() -> None:
    source_by_ref, manifest, reconstruction_read_model, _, reconstruction_inputs = _bound_inputs()
    manifest["outcome_cells"][0]["measurement_contract_ref"] = "MC:CASH:V1"
    thread_set = _thread_set(source_by_ref, manifest, reconstruction_read_model)
    relative_thread = thread_set["threads"][2]
    relative_thread["claim_type"] = "RELATIVE_CAUSAL"
    relative_thread["e3_comparative_requested"] = True
    before = deepcopy((manifest, reconstruction_read_model, thread_set))
    registry = sqlite3.connect(":memory:")
    j1.register_frozen_reconstruction(
        registry,
        reconstruction_read_model,
        reconstruction_inputs,
        frozen_at=datetime.now(timezone.utc).isoformat(),
    )

    j2_result = j2._compile_mechanism_thread_projection_with_registry(
        thread_set,
        episode_manifest=manifest,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert j2_result["valid"], j2_result["findings"]
    read_model = j2_result["mechanism_thread_read_model"]
    views = {view["thread_id"]: view for view in read_model["thread_views"]}
    forecast_thread_id = thread_set["threads"][0]["thread_id"]
    assert views[forecast_thread_id]["j3_forecast_eligible"] is True
    assert views[relative_thread["thread_id"]]["j3_forecast_eligible"] is False
    assert views[relative_thread["thread_id"]]["resolution_status"] == "RESOLVED"

    j3_result = j3._compile_forecast_projection_with_registry(
        manifest,
        _forecast_source(
            manifest,
            thread_set["thread_set_id"],
            forecast_thread_id,
            source_packet_ref=reconstruction_read_model["source_packet_ref"],
            source_id=read_model["thread_views"][0]["source_refs"][0]["source_ref"],
            available_at=read_model["thread_views"][0]["source_refs"][0]["available_at"],
        ),
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert j3_result["valid"], j3_result["findings"]
    forecast_projection = j3_result["forecast_projection"]
    assert forecast_projection["projection_state"] == "FORECAST_REQUESTS_READY"
    assert [request["thread_id"] for request in forecast_projection["forecast_requests"]] == [
        forecast_thread_id
    ]
    assert set(forecast_projection["rights"].values()) == {"NOT_AUTHORIZED"}

    j4_result = j4._compile_serialized_j2_thread_projection_with_registry(
        episode_manifest=manifest,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        mechanism_thread_set=thread_set,
        thread_id=relative_thread["thread_id"],
        target_trial_bindings=None,
        v5_candidate=None,
        reconstruction_registry=registry,
    )

    assert j4_result["projection_status"] == j4.NOT_ADMITTED
    assert j4_result["comparative_candidate"] is None
    assert j4_result["locality"] == {
        "applies_only_to_thread_id": relative_thread["thread_id"],
        "e0_e2_unaffected": True,
        "other_threads_unaffected": True,
        "industry_block_unaffected": True,
    }
    assert all(
        value is False
        for key, value in j4_result["authority"].items()
        if key != "pre_outcome_projection_only"
    )
    assert forecast_projection["projection_state"] == "FORECAST_REQUESTS_READY"
    assert read_model["claim_permissions"]
    assert (manifest, reconstruction_read_model, thread_set) == before
