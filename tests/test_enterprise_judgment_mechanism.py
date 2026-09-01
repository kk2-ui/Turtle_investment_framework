from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
import sqlite3

import pytest

from scripts import enterprise_judgment_mechanism as mechanism
from scripts import enterprise_judgment_reconstruction as reconstruction
from tests.test_enterprise_judgment_core import _ledger, _model
from tests.test_enterprise_judgment_reconstruction import (
    _contract,
    _episode_manifest,
    _source_inputs,
    _spec,
)


def _episode_thread(claim_id: str, role: str) -> dict:
    return {
        "thread_id": "THREAD:" + claim_id,
        "role": role,
        "claim_ids": [claim_id],
        "hypotheses": [
            {
                "hypothesis_id": "H-A:" + claim_id,
                "role": "H_A",
                "statement": "The cutoff-visible mechanism transmits through the stated operating boundary.",
            },
            {
                "hypothesis_id": "H-B:" + claim_id,
                "role": "H_B",
                "statement": "A competing cutoff-visible explanation better accounts for the same signal.",
            },
        ],
        "observation_clock_ref": "CLOCK:" + claim_id,
        "outcome_cell_ids": ["CELL:CASH"],
    }


def _bound_inputs(*, no_action: bool = False) -> tuple[dict, dict, dict, dict, dict]:
    source_receipt, source_package = _source_inputs()
    decision_contract = _contract(source_package)
    model = _model(source_package=source_package)
    ledger = _ledger()
    spec = _spec(source_package, decision_contract)
    if no_action:
        for enterprise_mechanism in model["mechanisms"]:
            enterprise_mechanism["management_decision_ids"] = []
        model["state_changes"][0]["management_decision_ids"] = []
        ledger["events"] = []
        for loop in spec["feedback_loops"]:
            loop["decision_ids"] = []
        spec["decision_ids"] = []
        spec["decision_observation"].update({
            "status": "NO_MATERIAL_DECISION_OBSERVED",
            "rationale": "The eligible cutoff packet supports enterprise state but no material action.",
        })
    compiled = reconstruction.compile_enterprise_reconstruction(
        spec,
        source_packet_receipt=source_receipt,
        source_package=source_package,
        enterprise_model=model,
        decision_ledger=ledger,
        decision_contract=decision_contract,
    )
    assert compiled["valid"], compiled["findings"]
    reconstruction_read_model = compiled["reconstruction"]
    reconstruction_inputs = {
        "spec": spec,
        "source_packet_receipt": source_receipt,
        "source_package": source_package,
        "enterprise_model": model,
        "decision_ledger": ledger,
        "decision_contract": decision_contract,
    }
    manifest = _episode_manifest(
        source_package,
        decision_contract,
        reconstruction_read_model["episode_component_refs"],
    )
    source_by_ref = {source["source_ref"]: source for source in source_package["sources"]}
    for index, claim in enumerate(manifest["claims"]):
        claim["admission_level"] = "E2_MECHANISM_PROBE"
        claim["cell_status"] = "OBSERVED" if index == 0 else "INFERRED"
        claim["evidence_refs"] = ["SRC:CASH" if claim["domain"] == "CASH" else "SRC:OPERATING"]
        claim["dependent_outcome_cell_ids"] = []
    manifest["mechanism_threads"] = [
        _episode_thread("CLAIM:OPERATIONS", "PRIMARY"),
        _episode_thread("CLAIM:CASH", "SUPPORTING"),
        _episode_thread("CLAIM:LIFECYCLE", "SUPPORTING"),
    ]
    return source_by_ref, manifest, reconstruction_read_model, decision_contract, reconstruction_inputs


def _thread_detail(
    episode_thread: dict,
    *,
    cutoff_at: str,
    source_ref: str,
    source_by_ref: dict[str, dict],
    loop_id: str,
    claim_type: str = "WITHIN_CASE_MECHANISM",
    evidence_ceiling: str = "MECHANISM",
    local_status: str = "INFERRED",
    e3_requested: bool = False,
) -> dict:
    cutoff = datetime.fromisoformat(cutoff_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    permitted_outputs = {
        "CONTEXT": ["RESEARCH_AGENDA"],
        "TEACHING": ["MECHANISM_VIEW", "TEACHING_ONLY", "RESEARCH_AGENDA"],
        "MECHANISM": ["MECHANISM_VIEW", "TEACHING_ONLY", "MECHANISM_CANDIDATE", "RESEARCH_AGENDA"],
    }[evidence_ceiling]
    if local_status in {"UNKNOWN", "EVIDENCE_INELIGIBLE", "NOT_APPLICABLE"}:
        permitted_outputs = ["RESEARCH_AGENDA"]
    return {
        "thread_id": episode_thread["thread_id"],
        "role": episode_thread["role"],
        "claim_ids": list(episode_thread["claim_ids"]),
        "claim_type": claim_type,
        "hypotheses": deepcopy(episode_thread["hypotheses"]),
        "responsibility_boundary": {
            "responsibility_unit_id": "UNIT:BUSINESS",
            "arena_id": "ARENA:CORE",
        },
        "reconstruction_loop_ids": [loop_id],
        "evidence_discriminator": {
            "discriminator_id": "DISC:" + episode_thread["thread_id"],
            "observable": "The predeclared operating or cash signal at the same responsibility boundary.",
            "expected_if_h_a": "The signal moves in the direction specified by H-A.",
            "expected_if_h_b": "The signal is absent or moves in the direction specified by H-B.",
        },
        "observation_clock": {
            "clock_id": episode_thread["observation_clock_ref"],
            "opens_at": cutoff.isoformat(),
            "due_at": (cutoff + timedelta(days=365)).isoformat(),
        },
        "outcome_cell_refs": list(episode_thread["outcome_cell_ids"]),
        "source_refs": [{
            "source_ref": source_ref,
            "available_at": source_by_ref[source_ref]["available_at"],
            "information_role": "CUTOFF_VISIBLE",
        }],
        "local_status": local_status,
        "evidence_ceiling": evidence_ceiling,
        "permitted_outputs": permitted_outputs,
        "e3_comparative_requested": e3_requested,
    }


def _thread_set(source_by_ref: dict[str, dict], manifest: dict, reconstruction_read_model: dict) -> dict:
    episode_threads = manifest["mechanism_threads"]
    return {
        "schema_version": mechanism.SCHEMA_VERSION,
        "thread_set_id": "J2:SYNTHETIC:THREADS",
        "episode_ref": {
            "episode_id": manifest["episode_id"],
            "schema_version": manifest["schema_version"],
        },
        "reconstruction_ref": {
            "reconstruction_id": reconstruction_read_model["reconstruction_id"],
            "schema_version": reconstruction_read_model["schema_version"],
        },
        "threads": [
            _thread_detail(
                episode_threads[0], cutoff_at=manifest["cutoff_at"],
                source_ref="SRC:OPERATING", source_by_ref=source_by_ref,
                loop_id="LOOP:CUSTOMER-ECONOMICS", local_status="OBSERVED",
            ),
            _thread_detail(
                episode_threads[1], cutoff_at=manifest["cutoff_at"],
                source_ref="SRC:CASH", source_by_ref=source_by_ref,
                loop_id="LOOP:ECONOMICS-CASH-LOSS", evidence_ceiling="TEACHING",
            ),
            _thread_detail(
                episode_threads[2], cutoff_at=manifest["cutoff_at"],
                source_ref="SRC:OPERATING", source_by_ref=source_by_ref,
                loop_id="LOOP:CUSTOMER-ECONOMICS", claim_type="DESCRIPTIVE_STRUCTURE",
                evidence_ceiling="TEACHING",
            ),
        ],
        "outcome_access": "NONE",
        "object_class": "ENTERPRISE_JUDGMENT_MECHANISM_THREAD_SET",
        "claim_class": "LOCAL_MECHANISM_THREADS",
        "allowed_outputs": list(mechanism.ALLOWED_OUTPUTS),
    }


def test_j2_projects_independent_thread_permissions_and_allows_e1_without_action() -> None:
    source_by_ref, manifest, reconstruction_read_model, _, reconstruction_inputs = _bound_inputs(no_action=True)
    thread_set = _thread_set(source_by_ref, manifest, reconstruction_read_model)
    before_manifest = deepcopy(manifest)
    before_reconstruction = deepcopy(reconstruction_read_model)

    result = mechanism._compile_mechanism_thread_projection_with_registry(
        thread_set,
        episode_manifest=manifest,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
    )

    assert result["valid"], result["findings"]
    read_model = result["mechanism_thread_read_model"]
    views = {view["thread_id"]: view for view in read_model["thread_views"]}
    assert views["THREAD:CLAIM:OPERATIONS"]["permitted_outputs"] == [
        "MECHANISM_VIEW", "TEACHING_ONLY", "MECHANISM_CANDIDATE", "RESEARCH_AGENDA",
    ]
    assert views["THREAD:CLAIM:CASH"]["permitted_outputs"] == [
        "MECHANISM_VIEW", "TEACHING_ONLY", "RESEARCH_AGENDA",
    ]
    assert all(view["j3_forecast_eligible"] for view in views.values())
    assert all(not view["j4_comparative_eligible"] for view in views.values())
    assert all(not view["e3_comparative_requested"] for view in views.values())
    assert read_model["forecast_authorization"] == "NOT_AUTHORIZED"
    assert read_model["comparative_authorization"] == "NOT_AUTHORIZED"
    assert read_model["investment_authorization"] == "NOT_AUTHORIZED"
    assert manifest == before_manifest
    assert reconstruction_read_model == before_reconstruction


def test_j2_localizes_unknown_source_binding_to_dependent_claim() -> None:
    source_by_ref, manifest, reconstruction_read_model, _, reconstruction_inputs = _bound_inputs()
    thread_set = _thread_set(source_by_ref, manifest, reconstruction_read_model)
    thread_set["threads"][1]["source_refs"][0]["source_ref"] = "SRC:UNKNOWN"

    result = mechanism._compile_mechanism_thread_projection_with_registry(
        thread_set,
        episode_manifest=manifest,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
    )

    assert result["valid"], result["findings"]
    read_model = result["mechanism_thread_read_model"]
    views = {view["thread_id"]: view for view in read_model["thread_views"]}
    assert views["THREAD:CLAIM:CASH"]["resolution_status"] == "BOUNDARY_ONLY"
    assert "SOURCE_REF_UNKNOWN:SRC:UNKNOWN" in views["THREAD:CLAIM:CASH"]["binding_findings"]
    permissions = {row["claim_id"]: row for row in read_model["claim_permissions"]}
    assert permissions["CLAIM:CASH"]["allowed_outputs"] == ["RESEARCH_AGENDA"]
    assert "MECHANISM_CANDIDATE" in permissions["CLAIM:OPERATIONS"]["allowed_outputs"]
    assert "TEACHING_ONLY" in permissions["CLAIM:LIFECYCLE"]["allowed_outputs"]


def test_j2_missing_episode_thread_detail_blocks_only_that_threads_claim() -> None:
    source_by_ref, manifest, reconstruction_read_model, _, reconstruction_inputs = _bound_inputs()
    extra_claim = {
        "claim_id": "CLAIM:COMPETITION",
        "question_id": "Q:OPERATIONS",
        "domain": "COMPETITION",
        "statement": "Competitive response remains a local supporting mechanism question.",
        "cell_status": "INFERRED",
        "admission_level": "E2_MECHANISM_PROBE",
        "evidence_refs": ["SRC:OPERATING"],
        "dependent_outcome_cell_ids": [],
    }
    manifest["claims"].append(extra_claim)
    manifest["question_set"][0]["claim_ids"].append(extra_claim["claim_id"])
    manifest["mechanism_threads"].append(_episode_thread(extra_claim["claim_id"], "SUPPORTING"))
    thread_set = _thread_set(source_by_ref, manifest, reconstruction_read_model)

    result = mechanism._compile_mechanism_thread_projection_with_registry(
        thread_set,
        episode_manifest=manifest,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
    )

    assert result["valid"], result["findings"]
    read_model = result["mechanism_thread_read_model"]
    missing = next(view for view in read_model["thread_views"] if view["thread_id"] == "THREAD:CLAIM:COMPETITION")
    assert missing["binding_findings"] == ["THREAD_DETAIL_MISSING"]
    permissions = {row["claim_id"]: row for row in read_model["claim_permissions"]}
    assert permissions["CLAIM:COMPETITION"]["allowed_outputs"] == ["RESEARCH_AGENDA"]
    assert "MECHANISM_CANDIDATE" in permissions["CLAIM:OPERATIONS"]["allowed_outputs"]


def test_j2_marks_explicit_e3_request_without_running_comparative_or_forecast() -> None:
    source_by_ref, manifest, reconstruction_read_model, _, reconstruction_inputs = _bound_inputs()
    thread_set = _thread_set(source_by_ref, manifest, reconstruction_read_model)
    manifest["outcome_cells"][0]["measurement_contract_ref"] = "METRIC:CASH"
    thread_set["threads"][0]["claim_type"] = "RELATIVE_CAUSAL"
    thread_set["threads"][0]["e3_comparative_requested"] = True
    primary = thread_set["threads"][0]
    primary["comparative_projection_contract"] = {
        "hypothesis_bindings": [
            {
                "role": hypothesis["role"],
                "j2_hypothesis_id": hypothesis["hypothesis_id"],
                "j2_statement": hypothesis["statement"],
                "v5_hypothesis_id": hypothesis["hypothesis_id"],
                "v5_mechanism": hypothesis["statement"],
            }
            for hypothesis in primary["hypotheses"]
        ],
        "outcome_bindings": [{
            "outcome_cell_id": "CELL:CASH",
            "measurement_contract_ref": "METRIC:CASH",
            "v5_measurement_contracts": [{"metric_id": "METRIC:CASH"}],
        }],
        "source_lineage": {
            "j1_source_packet_refs": [deepcopy(reconstruction_read_model["source_packet_ref"])],
            "j2_source_refs": deepcopy(primary["source_refs"]),
            "v5_source_provenance": {"h2": {"receipt_id": "H2:SYNTHETIC"}},
            "v5_sources": [{"source_id": "V5:SYNTHETIC"}],
        },
    }

    result = mechanism._compile_mechanism_thread_projection_with_registry(
        thread_set,
        episode_manifest=manifest,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
    )

    assert result["valid"], result["findings"]
    primary = result["mechanism_thread_read_model"]["thread_views"][0]
    assert primary["e3_comparative_requested"] is True
    assert primary["j3_forecast_eligible"] is False
    assert primary["j4_comparative_eligible"] is True
    assert primary["forecast_performed"] is False
    assert primary["comparative_performed"] is False


def test_j2_keeps_a_missing_comparative_bridge_local_to_j4() -> None:
    source_by_ref, manifest, reconstruction_read_model, _, reconstruction_inputs = _bound_inputs()
    thread_set = _thread_set(source_by_ref, manifest, reconstruction_read_model)
    thread_set["threads"][0]["claim_type"] = "RELATIVE_CAUSAL"
    thread_set["threads"][0]["e3_comparative_requested"] = True

    result = mechanism._compile_mechanism_thread_projection_with_registry(
        thread_set,
        episode_manifest=manifest,
        reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
    )

    assert result["valid"], result["findings"]
    primary = result["mechanism_thread_read_model"]["thread_views"][0]
    assert primary["resolution_status"] == "RESOLVED"
    assert primary["j4_comparative_eligible"] is False
    assert primary["comparative_contract_findings"] == [
        "COMPARATIVE_PROJECTION_CONTRACT_REQUIRED"
    ]
    assert "MECHANISM_CANDIDATE" in primary["permitted_outputs"]


def test_j2_rejects_price_return_post_cutoff_leakage_and_universal_quality_upgrade() -> None:
    source_by_ref, manifest, reconstruction_read_model, _, reconstruction_inputs = _bound_inputs()
    thread_set = _thread_set(source_by_ref, manifest, reconstruction_read_model)

    price_leak = deepcopy(thread_set)
    price_leak["threads"][0]["hypotheses"][0]["statement"] = "The later stock return proves H-A."
    result = mechanism._validate_mechanism_thread_set_with_registry(
        price_leak, episode_manifest=manifest, reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
    )
    assert not result["valid"]
    assert "mechanism_thread_set.threads[0].pre_outcome_narrative_contains_price_return_or_post_cutoff_leakage" in result["findings"]

    operating_return = deepcopy(thread_set)
    operating_return["threads"][0]["hypotheses"][0]["statement"] = (
        "Capital investment return improves only if utilization and unit economics improve."
    )
    result = mechanism._validate_mechanism_thread_set_with_registry(
        operating_return, episode_manifest=manifest, reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
    )
    assert result["valid"], result["findings"]

    post_cutoff = deepcopy(thread_set)
    cutoff = datetime.fromisoformat(manifest["cutoff_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
    post_cutoff["threads"][1]["source_refs"][0]["available_at"] = (cutoff + timedelta(days=1)).isoformat()
    result = mechanism._validate_mechanism_thread_set_with_registry(
        post_cutoff, episode_manifest=manifest, reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
    )
    assert not result["valid"]
    assert "mechanism_thread_set.threads[1].source_refs[0].source_must_be_available_at_or_before_cutoff" in result["findings"]

    universal = deepcopy(thread_set)
    universal["threads"][2]["hypotheses"][0]["statement"] = "This proves the issuer is an overall high-quality company."
    result = mechanism._validate_mechanism_thread_set_with_registry(
        universal, episode_manifest=manifest, reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
    )
    assert not result["valid"]
    assert "mechanism_thread_set.threads[2].universal_company_quality_upgrade_prohibited" in result["findings"]


def test_j2_rejects_unpaired_hypotheses_permissions_and_implicit_comparative_request() -> None:
    source_by_ref, manifest, reconstruction_read_model, _, reconstruction_inputs = _bound_inputs()
    thread_set = _thread_set(source_by_ref, manifest, reconstruction_read_model)

    malformed = deepcopy(thread_set)
    malformed["threads"][0]["hypotheses"][1]["role"] = "H_A"
    malformed["threads"][1]["permitted_outputs"] = ["MECHANISM_CANDIDATE", "RESEARCH_AGENDA"]
    malformed["threads"][2]["e3_comparative_requested"] = True
    result = mechanism._validate_mechanism_thread_set_with_registry(
        malformed, episode_manifest=manifest, reconstruction_read_model=reconstruction_read_model,
        reconstruction_inputs=reconstruction_inputs,
    )

    assert not result["valid"]
    assert "mechanism_thread_set.threads[0].hypotheses_must_distinguish_h_a_h_b" in result["findings"]
    assert "mechanism_thread_set.threads[1].permitted_outputs_must_match_local_status_and_evidence_ceiling" in result["findings"]
    assert "mechanism_thread_set.threads[2].relative_causal_claim_and_e3_request_must_match" in result["findings"]


def test_j2_schema_is_closed_and_carries_no_forecast_or_comparative_output() -> None:
    schema = json.loads(Path("schemas/enterprise_judgment_mechanism_thread.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["threads"]["minItems"] == 3
    assert schema["properties"]["threads"]["maxItems"] == 5
    assert schema["properties"]["allowed_outputs"]["const"] == mechanism.ALLOWED_OUTPUTS
    assert "comparative_projection_contract" in schema["$defs"]["thread"]["properties"]
    assert schema["$defs"]["comparative_outcome_binding"]["properties"][
        "v5_measurement_contracts"
    ]["maxItems"] == 1
    assert "FORECAST" not in mechanism.ALLOWED_OUTPUTS
    assert "COMPARATIVE" not in mechanism.ALLOWED_OUTPUTS


def test_j2_public_api_accepts_only_a_frozen_j1_identity() -> None:
    assert tuple(inspect.signature(mechanism.compile_mechanism_thread_projection).parameters) == (
        "thread_set",
        "episode_manifest",
        "reconstruction_ref",
    )


def test_j2_public_api_reads_the_preexisting_canonical_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_by_ref, manifest, reconstruction_read_model, _, reconstruction_inputs = _bound_inputs()
    thread_set = _thread_set(source_by_ref, manifest, reconstruction_read_model)
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

    result = mechanism.compile_mechanism_thread_projection(
        thread_set,
        episode_manifest=manifest,
        reconstruction_ref=thread_set["reconstruction_ref"],
    )

    assert result["valid"], result["findings"]
    assert result["mechanism_thread_read_model"]["thread_set_id"] == thread_set["thread_set_id"]


def test_j2_public_api_rejects_when_the_canonical_registry_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_by_ref, manifest, reconstruction_read_model, _, _ = _bound_inputs()
    thread_set = _thread_set(source_by_ref, manifest, reconstruction_read_model)
    monkeypatch.setattr(reconstruction, "CANONICAL_REGISTRY_PATH", tmp_path / "missing.db")

    result = mechanism.compile_mechanism_thread_projection(
        thread_set,
        episode_manifest=manifest,
        reconstruction_ref=thread_set["reconstruction_ref"],
    )

    assert not result["valid"]
    assert result["mechanism_thread_read_model"] is None
    assert result["findings"] == [
        "reconstruction_registry:canonical_frozen_reconstruction_registry_unavailable"
    ]
