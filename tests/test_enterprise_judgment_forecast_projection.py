from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
import sqlite3

import pytest

from scripts import enterprise_judgment_forecast_projection as projection
from scripts import enterprise_judgment_reconstruction as reconstruction
from scripts import enterprise_judgment_source_packet as source_packet
from tests.test_enterprise_judgment_mechanism import (
    _bound_inputs as _j2_bound_inputs,
    _thread_set,
)


def _context() -> tuple[dict, dict, dict, dict, sqlite3.Connection]:
    source_by_ref, manifest, reconstruction_read_model, _, reconstruction_inputs = _j2_bound_inputs()
    manifest["outcome_cells"] = [
        {
            "outcome_cell_id": "CELL:OPERATING",
            "dimension": "OPERATIONS",
            "status": "UNKNOWN",
            "measurement_contract_ref": "MC:OPERATING:V1",
            "custodian_receipt_ref": "",
        },
        {
            "outcome_cell_id": "CELL:CASH",
            "dimension": "CASH",
            "status": "UNKNOWN",
            "measurement_contract_ref": "MC:CASH:V1",
            "custodian_receipt_ref": "",
        },
        {
            "outcome_cell_id": "CELL:LOSS",
            "dimension": "PERMANENT_LOSS",
            "status": "EVIDENCE_INELIGIBLE",
            "measurement_contract_ref": "MC:LOSS:V1",
            "custodian_receipt_ref": "",
        },
    ]
    cell_ids = ["CELL:OPERATING", "CELL:CASH", "CELL:LOSS"]
    for thread, cell_id in zip(manifest["mechanism_threads"], cell_ids, strict=True):
        thread["outcome_cell_ids"] = [cell_id]
    thread_set = _thread_set(source_by_ref, manifest, reconstruction_read_model)
    registry = sqlite3.connect(":memory:")
    reconstruction.register_frozen_reconstruction(
        registry,
        reconstruction_read_model,
        reconstruction_inputs,
        frozen_at=datetime.now(timezone.utc).isoformat(),
    )
    return manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry


def _evidence(*, source_ref: str, available_at: str, suffix: str) -> list[dict]:
    return [{
        "source_id": source_ref,
        "published_at": available_at[:10],
        "available_at": available_at,
        "field_ref": "Official cutoff-visible filing p12.",
        "field_id": "FIELD:" + suffix,
    }]


def _cell(
    manifest: dict,
    *,
    request_id: str,
    outcome_cell_id: str,
    forecast_dimension_id: str,
    window_id: str,
    request_kind: str,
    measurement_contract_id: str,
    source_ref: str,
    available_at: str,
) -> dict:
    value = {
        "request_id": request_id,
        "outcome_cell_id": outcome_cell_id,
        "forecast_eligible": True,
        "forecast_dimension_id": forecast_dimension_id,
        "window_id": window_id,
        "request_kind": request_kind,
        "measurement_ref": {
            "measurement_contract_id": measurement_contract_id,
            "measurement_contract_version": 1,
            "measurement_id": "MEASURE:" + request_id,
        },
        "evidence_refs": _evidence(
            source_ref=source_ref,
            available_at=available_at,
            suffix=request_id,
        ),
    }
    if request_kind != "ABSTAIN":
        value["baseline_reference"] = "Cutoff risk-set baseline only."
    return value


def _source(manifest: dict, reconstruction_read_model: dict, thread_set: dict) -> dict:
    source_refs = [thread["source_refs"][0] for thread in thread_set["threads"]]
    ordinal = _cell(
        manifest,
        request_id="REQ:OPERATING:ONE_YEAR",
        outcome_cell_id="CELL:OPERATING",
        forecast_dimension_id="NORMAL_EARNINGS",
        window_id="ONE_YEAR",
        request_kind="ORDINAL_PROBABILITY",
        measurement_contract_id="MC:OPERATING:V1",
        source_ref=source_refs[0]["source_ref"],
        available_at=source_refs[0]["available_at"],
    )
    interval = _cell(
        manifest,
        request_id="REQ:CASH:THREE_YEAR",
        outcome_cell_id="CELL:CASH",
        forecast_dimension_id="CASH_CONVERSION_AND_CAPEX_BURDEN",
        window_id="THREE_YEAR",
        request_kind="NUMERIC_INTERVAL",
        measurement_contract_id="MC:CASH:V1",
        source_ref=source_refs[1]["source_ref"],
        available_at=source_refs[1]["available_at"],
    )
    interval.update({"interval_coverage": 0.8, "interval_unit": "RATIO"})
    abstain = _cell(
        manifest,
        request_id="REQ:LOSS:FIVE_YEAR",
        outcome_cell_id="CELL:LOSS",
        forecast_dimension_id="PERMANENT_LOSS_RISK",
        window_id="FIVE_YEAR",
        request_kind="ABSTAIN",
        measurement_contract_id="MC:LOSS:V1",
        source_ref=source_refs[2]["source_ref"],
        available_at=source_refs[2]["available_at"],
    )
    abstain["abstain_reason"] = "The cutoff packet cannot support a probability without inventing evidence."
    return {
        "schema_version": projection.SOURCE_SCHEMA_VERSION,
        "projection_id": "J3:SYNTHETIC:EPISODE:V1",
        "episode_ref": {
            "episode_id": manifest["episode_id"],
            "company_id": manifest["company_id"],
            "issuer_id": manifest["issuer_id"],
            "cutoff_at": manifest["cutoff_at"],
        },
        "mechanism_thread_set_ref": {
            "thread_set_id": "J2:SYNTHETIC:THREADS",
            "schema_version": projection.J2_SCHEMA_VERSION,
        },
        "source_packet_refs": [deepcopy(reconstruction_read_model["source_packet_ref"])],
        "threads": [
            {
                "thread_id": "THREAD:CLAIM:OPERATIONS",
                "cells": [ordinal],
            },
            {
                "thread_id": "THREAD:CLAIM:CASH",
                "cells": [interval],
            },
            {
                "thread_id": "THREAD:CLAIM:LIFECYCLE",
                "cells": [abstain],
            },
        ],
        "object_class": "ENTERPRISE_JUDGMENT_FORECAST_PROJECTION_SOURCE",
        "claim_class": "J2_FORECAST_ELIGIBILITY_ROUTING",
        "allowed_outputs": list(projection.ALLOWED_OUTPUTS),
    }


def test_j3_projects_probability_interval_and_abstain_requests_without_running_forecast() -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    before_manifest = deepcopy(manifest)
    before_source = deepcopy(source)
    before_reconstruction = deepcopy(reconstruction_read_model)
    before_thread_set = deepcopy(thread_set)

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert result["valid"], result["findings"]
    projected = result["forecast_projection"]
    assert projected["projection_state"] == "FORECAST_REQUESTS_READY"
    assert len(projected["forecast_requests"]) == 3
    requests = {request["request_id"]: request for request in projected["forecast_requests"]}
    assert requests["REQ:OPERATING:ONE_YEAR"]["response_contract"] == {
        "request_kind": "ORDINAL_PROBABILITY",
        "evidence_status": "MODEL_UNCERTAIN",
        "labels": ["DETERIORATE", "STABLE", "IMPROVE"],
        "probabilities_must_sum_to_one": True,
    }
    assert requests["REQ:CASH:THREE_YEAR"]["response_contract"] == {
        "request_kind": "NUMERIC_INTERVAL",
        "evidence_status": "MODEL_UNCERTAIN",
        "interval_coverage": 0.8,
        "unit": "RATIO",
        "engine_adapter_state": "REQUEST_ONLY",
    }
    loss = requests["REQ:LOSS:FIVE_YEAR"]
    assert loss["response_contract"]["evidence_status"] == "EVIDENCE_INELIGIBLE"
    assert loss["coverage_permission"]["settlement_statuses"] == ["EVIDENCE_INELIGIBLE"]
    assert loss["error_attribution_permission"]["direct_learning_scopes"] == ["COVERAGE"]
    assert requests["REQ:OPERATING:ONE_YEAR"]["measurement_ref"] == source["threads"][0]["cells"][0]["measurement_ref"]
    assert requests["REQ:OPERATING:ONE_YEAR"]["evidence_refs"] == source["threads"][0]["cells"][0]["evidence_refs"]
    assert projected["episode_ref"] == source["episode_ref"]
    assert projected["mechanism_thread_set_ref"] == source["mechanism_thread_set_ref"]
    assert projected["source_packet_refs"] == source["source_packet_refs"]
    assert projected["preserved_admission"] == {
        "E0_CONTEXT": "PRESERVED",
        "E1_RECONSTRUCTION": "PRESERVED",
    }
    assert set(projected["rights"].values()) == {"NOT_AUTHORIZED"}
    assert projected["allowed_outputs"] == ["FORECAST_REQUESTS_ONLY", "RESEARCH_AGENDA"]
    assert manifest == before_manifest
    assert source == before_source
    assert reconstruction_read_model == before_reconstruction
    assert thread_set == before_thread_set


def test_j3_selects_only_explicitly_eligible_threads_and_cells() -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    thread_set["threads"][0]["source_refs"][0]["source_ref"] = "SRC:UNKNOWN"
    source["threads"][1]["cells"][0]["forecast_eligible"] = False

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert result["valid"], result["findings"]
    requests = result["forecast_projection"]["forecast_requests"]
    assert [request["request_id"] for request in requests] == ["REQ:LOSS:FIVE_YEAR"]
    rejected = result["forecast_projection"]["cell_rejections"]
    assert rejected[0]["request_id"] == "REQ:OPERATING:ONE_YEAR"
    assert any("j2_thread_not_forecast_eligible" in reason for reason in rejected[0]["reasons"])


def test_j3_binary_probability_request_preserves_the_frozen_event_statement() -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    cell = source["threads"][0]["cells"][0]
    cell["request_kind"] = "BINARY_PROBABILITY"
    cell["event_statement"] = "Normal earnings remain positive at the frozen one-year measurement date."

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert result["valid"], result["findings"]
    request = result["forecast_projection"]["forecast_requests"][0]
    assert request["response_contract"] == {
        "request_kind": "BINARY_PROBABILITY",
        "evidence_status": "MODEL_UNCERTAIN",
        "event_statement": cell["event_statement"],
    }


def test_j3_empty_eligible_set_is_explicit_and_preserves_e0_e1() -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    source["threads"] = []

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert result["valid"], result["findings"]
    projected = result["forecast_projection"]
    assert projected["projection_state"] == "NO_FORECAST_ELIGIBLE_CELLS"
    assert projected["forecast_requests"] == []
    assert projected["cell_rejections"] == []
    assert projected["preserved_admission"]["E0_CONTEXT"] == "PRESERVED"
    assert projected["preserved_admission"]["E1_RECONSTRUCTION"] == "PRESERVED"


def test_j3_cell_identity_and_measurement_mismatches_remain_local() -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    missing = deepcopy(source["threads"][0]["cells"][0])
    missing.update({"request_id": "REQ:MISSING", "outcome_cell_id": "CELL:MISSING"})
    mismatched = deepcopy(source["threads"][1]["cells"][0])
    mismatched["request_id"] = "REQ:CASH:MISMATCH"
    mismatched["measurement_ref"]["measurement_contract_id"] = "MC:OTHER:V1"
    source["threads"][0]["cells"].append(missing)
    source["threads"][1]["cells"].append(mismatched)

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert result["valid"], result["findings"]
    projected = result["forecast_projection"]
    assert len(projected["forecast_requests"]) == 3
    rejected = {item["request_id"]: item["reasons"] for item in projected["cell_rejections"]}
    assert any("outcome_cell_id_not_in_episode" in reason for reason in rejected["REQ:MISSING"])
    assert any("measurement_contract_id_must_match_episode_cell" in reason for reason in rejected["REQ:CASH:MISMATCH"])
    assert projected["preserved_admission"] == {
        "E0_CONTEXT": "PRESERVED",
        "E1_RECONSTRUCTION": "PRESERVED",
    }


def test_j3_rejects_post_cutoff_evidence_locally_without_dropping_siblings() -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    cutoff = datetime.fromisoformat(manifest["cutoff_at"].replace("Z", "+00:00"))
    evidence = source["threads"][1]["cells"][0]["evidence_refs"][0]
    evidence["published_at"] = cutoff.date().isoformat()
    evidence["available_at"] = (cutoff + timedelta(seconds=1)).isoformat()

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert result["valid"], result["findings"]
    projected = result["forecast_projection"]
    assert {request["request_id"] for request in projected["forecast_requests"]} == {
        "REQ:OPERATING:ONE_YEAR",
        "REQ:LOSS:FIVE_YEAR",
    }
    assert len(projected["cell_rejections"]) == 1
    assert any("post_cutoff_evidence_rejected" in reason for reason in projected["cell_rejections"][0]["reasons"])


def test_j3_allows_publication_date_before_the_exact_cutoff_safe_availability_instant() -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    evidence = source["threads"][0]["cells"][0]["evidence_refs"][0]
    available = datetime.fromisoformat(evidence["available_at"].replace("Z", "+00:00"))
    evidence["published_at"] = (available - timedelta(days=2)).date().isoformat()

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert result["valid"], result["findings"]
    assert len(result["forecast_projection"]["forecast_requests"]) == 3
    assert result["forecast_projection"]["cell_rejections"] == []


def test_j3_rejects_forged_eligibility_source_and_economic_dimension_locally() -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    cash_cell = source["threads"][1]["cells"][0]
    cash_cell["evidence_refs"][0]["source_id"] = "SOURCE:NOT-IN-J2"
    cash_cell["forecast_dimension_id"] = "PERMANENT_LOSS_RISK"

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert result["valid"], result["findings"]
    projected = result["forecast_projection"]
    assert [request["request_id"] for request in projected["forecast_requests"]] == [
        "REQ:OPERATING:ONE_YEAR",
        "REQ:LOSS:FIVE_YEAR",
    ]
    rejected = {item["request_id"]: item["reasons"] for item in projected["cell_rejections"]}
    assert any("source_id_not_bound_to_j2_thread" in reason for reason in rejected["REQ:CASH:THREE_YEAR"])
    assert any(
        "forecast_dimension_incompatible_with_outcome_domain" in reason
        for reason in rejected["REQ:CASH:THREE_YEAR"]
    )


def test_j3_rejects_price_return_payload_and_episode_identity_replacement() -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    contaminated = _source(manifest, reconstruction_read_model, thread_set)
    contaminated["threads"][0]["cells"][0]["price"] = 12.5

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        contaminated,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert not result["valid"]
    assert result["forecast_projection"] is None
    assert any("forbidden_price_return_outcome_or_valuation_field" in finding for finding in result["findings"])

    wrong_company = _source(manifest, reconstruction_read_model, thread_set)
    wrong_company["episode_ref"]["company_id"] = "CN:OTHER"
    result = projection._compile_forecast_projection_with_registry(
        manifest,
        wrong_company,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )
    assert not result["valid"]
    assert "projection_source.episode_ref.company_id_must_match_episode" in result["findings"]


def test_j3_rejects_invented_source_packet_lineage() -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    source["source_packet_refs"] = [{
        "receipt_id": "RECEIPT:INVENTED",
        "receipt_version": 1,
    }]

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert not result["valid"]
    assert result["forecast_projection"] is None
    assert "projection_source.source_packet_refs_must_match_j2_lineage" in result["findings"]


@pytest.mark.parametrize("forgery", ["RECEIPT", "SOURCE"])
def test_j3_rejects_a_synchronously_forged_j1_reconstruction(forgery: str) -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    forged_reconstruction = deepcopy(reconstruction_read_model)
    forged_thread_set = deepcopy(thread_set)
    if forgery == "RECEIPT":
        forged_ref = {"receipt_id": "RECEIPT:FORGED-BUT-SHAPED", "receipt_version": 7}
        forged_reconstruction["source_packet_ref"] = deepcopy(forged_ref)
        source["source_packet_refs"] = [deepcopy(forged_ref)]
    else:
        invented = deepcopy(forged_reconstruction["evidence_coverage"]["sources"][0])
        invented["source_ref"] = "SRC:INVENTED"
        forged_reconstruction["evidence_coverage"]["sources"].append(invented)
        forged_thread_set["threads"][0]["source_refs"][0]["source_ref"] = "SRC:INVENTED"
        source["threads"][0]["cells"][0]["evidence_refs"][0]["source_id"] = "SRC:INVENTED"

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        source,
        mechanism_thread_set=forged_thread_set,
        reconstruction_read_model=forged_reconstruction,
        reconstruction_inputs=reconstruction_inputs,
        reconstruction_registry=registry,
    )

    assert not result["valid"]
    assert result["forecast_projection"] is None
    assert any(
        "j2:reconstruction_proof:reconstruction_must_equal_bound_cutoff_safe_compilation" in finding
        for finding in result["findings"]
    )


def test_j3_rejects_a_fully_recompiled_replacement_of_registered_j1() -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, registry = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    forged_inputs = deepcopy(reconstruction_inputs)
    forged_ref = {"receipt_id": "SP:FORGED:SYNCHRONIZED", "receipt_version": 1}
    forged_inputs["source_packet_receipt"]["packet_id"] = forged_ref["receipt_id"]
    projected = source_packet.compile_core_source_package(forged_inputs["source_packet_receipt"])
    assert projected["valid"], projected["findings"]
    forged_inputs["source_package"] = projected["source_package"]
    forged_inputs["spec"]["source_packet_ref"] = deepcopy(forged_ref)
    forged_inputs["decision_contract"]["evidence_budget"]["source_packet_refs"] = [
        deepcopy(forged_ref)
    ]
    forged_inputs["enterprise_model"]["source_package_id"] = forged_ref["receipt_id"]
    compiled = reconstruction.compile_enterprise_reconstruction(
        forged_inputs["spec"],
        source_packet_receipt=forged_inputs["source_packet_receipt"],
        source_package=forged_inputs["source_package"],
        enterprise_model=forged_inputs["enterprise_model"],
        decision_ledger=forged_inputs["decision_ledger"],
        decision_contract=forged_inputs["decision_contract"],
    )
    assert compiled["valid"], compiled["findings"]
    source["source_packet_refs"] = [deepcopy(forged_ref)]

    result = projection._compile_forecast_projection_with_registry(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_read_model=compiled["reconstruction"],
        reconstruction_inputs=forged_inputs,
        reconstruction_registry=registry,
    )

    assert not result["valid"]
    assert result["forecast_projection"] is None
    assert "j2:reconstruction_registry:reconstruction_must_match_frozen_registry_object" in result["findings"]
    assert "j2:reconstruction_registry:reconstruction_inputs_must_match_frozen_registry_object" in result["findings"]


def test_j3_public_api_resolves_only_a_frozen_j1_identity() -> None:
    assert tuple(inspect.signature(projection.compile_forecast_projection).parameters) == (
        "episode_manifest",
        "projection_source",
        "mechanism_thread_set",
        "reconstruction_ref",
    )


def test_j3_requires_the_canonical_frozen_j1_registry_for_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, _ = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    monkeypatch.setattr(
        reconstruction,
        "CANONICAL_REGISTRY_PATH",
        tmp_path / "missing-canonical.db",
    )

    result = projection.compile_forecast_projection(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_ref=thread_set["reconstruction_ref"],
    )

    assert not result["valid"]
    assert result["forecast_projection"] is None
    assert result["findings"] == [
        "reconstruction_registry:canonical_frozen_reconstruction_registry_unavailable"
    ]


def test_j3_public_api_reads_the_preexisting_canonical_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, _ = _context()
    source = _source(manifest, reconstruction_read_model, thread_set)
    registry_path = tmp_path / "canonical.db"
    registry = sqlite3.connect(registry_path)
    reconstruction.register_frozen_reconstruction(
        registry,
        reconstruction_read_model,
        reconstruction_inputs,
        frozen_at=datetime.now(timezone.utc).isoformat(),
    )
    registry.close()
    monkeypatch.setattr(reconstruction, "CANONICAL_REGISTRY_PATH", registry_path)

    result = projection.compile_forecast_projection(
        manifest,
        source,
        mechanism_thread_set=thread_set,
        reconstruction_ref=thread_set["reconstruction_ref"],
    )

    assert result["valid"], result["findings"]
    assert result["forecast_projection"]["projection_state"] == "FORECAST_REQUESTS_READY"


def test_j3_schema_is_closed_and_formalizes_the_minimal_serialized_source_protocol() -> None:
    schema = json.loads(
        Path("schemas/enterprise_judgment_forecast_projection.schema.json").read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    assert schema["properties"]["allowed_outputs"]["const"] == projection.ALLOWED_OUTPUTS
    assert "projection_source_protocol" in schema["$defs"]
    assert schema["$defs"]["projection_source_protocol"]["additionalProperties"] is False
    assert "mechanism_thread_read_model_protocol" in schema["$defs"]
    assert "source_packet_refs" in schema["$defs"]["mechanism_thread_read_model_protocol"]["required"]
    assert "available_at" in schema["$defs"]["evidence_ref"]["required"]
    assert schema["$defs"]["numeric_interval_response"]["properties"]["engine_adapter_state"]["const"] == "REQUEST_ONLY"
    rights = schema["$defs"]["rights"]["properties"]
    assert set(rights) == {"causal", "comparative", "cjo", "method_freeze", "report", "valuation", "investment"}
    assert {value["const"] for value in rights.values()} == {"NOT_AUTHORIZED"}
