from __future__ import annotations

import inspect
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pytest

from scripts import enterprise_judgment_comparative_projection as j4
from scripts import enterprise_judgment_reconstruction as j1
from scripts import enterprise_judgment_source_packet as source_packet
from scripts import judgment_selection_v5 as v5
from tests.test_enterprise_judgment_mechanism import (
    _bound_inputs as _j2_bound_inputs,
    _thread_set as _j2_thread_set,
)
from tests.test_judgment_selection_v5 import _bundle, _refresh_reviewed_selection_contract


def _request() -> dict:
    candidate = _bundle()
    action = candidate["action_scope"]
    cohort = candidate["cohort_snapshot"]
    panel = candidate["counterfactual_panel"]
    members = panel["members"]
    time_contract = candidate["time_contract"]
    metrics_by_clock = {
        metric["clock"]: metric["metric_id"] for metric in candidate["measurement_contracts"]
    }
    target_member = next(
        member for member in cohort["members"]
        if member["issuer_id"] == action["focal_issuer_id"]
    )
    return {
        "schema_version": j4.REQUEST_SCHEMA_VERSION,
        "episode_ref": {
            "episode_id": "EJE:SYNTHETIC:TARGET:20201231",
            "company_id": target_member["company_id"],
            "issuer_id": action["focal_issuer_id"],
            "cutoff_at": time_contract["research_cutoff_at"],
        },
        "thread_ref": {
            "thread_id": "THREAD:RELATIVE:NETWORK",
            "claim_class": j4.RELATIVE_CAUSAL,
            "requested_admission_level": j4.E3_COMPARATIVE_LAB,
            "claim_ids": ["CLAIM:RELATIVE:D3", "CLAIM:RELATIVE:D4"],
            "hypothesis_ids": {
                "h_a": action["h_a"]["hypothesis_id"],
                "h_b": action["h_b"]["hypothesis_id"],
            },
            "responsibility_boundary": {
                "responsibility_unit_id": target_member["responsibility_unit_id"],
                "arena_id": candidate["competitive_arena"]["competitive_arena_id"],
            },
            "outcome_cell_ids": ["CELL:D3", "CELL:D4"],
        },
        "target_trial_bindings": {
            "action_exposure": {
                "action_id": action["action_id"],
                "focal_issuer_id": action["focal_issuer_id"],
                "exposure_start": action["action_effective_window"]["start"],
                "economic_carrier_ids": [
                    carrier["carrier_id"] for carrier in action["economic_carriers"]
                ],
                "scope_bridge_ids": [
                    bridge["scope_bridge_id"] for bridge in candidate["scope_bridges"]
                ],
            },
            "eligibility_time_zero": {
                "cohort_snapshot_id": cohort["cohort_snapshot_id"],
                "eligibility_as_of": time_contract["cohort_eligibility_as_of"],
                "time_zero": time_contract["action_effective_window"]["start"],
                "decision_observable_at": time_contract["decision_observable_at"],
            },
            "comparator_roles": {
                "counterfactual_panel_id": panel["counterfactual_panel_id"],
                "external_shock_comparator_ids": [
                    member["issuer_id"] for member in members
                    if member["causal_role"] == "EXTERNAL_SHOCK_COMPARATOR"
                ],
                "witness_ids": [
                    member["issuer_id"] for member in members
                    if member["causal_role"] == "EQUILIBRIUM_RESPONSE_WITNESS"
                ],
                "falsifier_ids": [
                    member["issuer_id"] for member in members
                    if member["causal_role"] == "FALSIFIER"
                ],
            },
            "outcome_follow_up": {
                "metric_ids_by_clock": metrics_by_clock,
                "economic_periods": deepcopy(time_contract["metric_economic_periods"]),
                "outcome_window_id": time_contract["outcome_window_id"],
                "minimum_decision_exposure_rule": time_contract["minimum_decision_exposure_rule"],
            },
            "censoring_interference": {
                "censoring_rule": j4.CENSORING_RULE,
                "non_replacement_rule": panel["non_replacement_rule"],
                "member_assumptions": [
                    {
                        "issuer_id": member["issuer_id"],
                        "parallel_action": member["parallel_action"],
                        "target_action_spillover": member["target_action_spillover"],
                    }
                    for member in members
                ],
            },
            "estimand": {
                "estimand_id": "ESTIMAND:RELATIVE:D3-D4",
                "target_issuer_id": action["focal_issuer_id"],
                "action_id": action["action_id"],
                "comparator_role": "EXTERNAL_SHOCK_COMPARATOR",
                "metric_ids_by_clock": metrics_by_clock,
                "contrast": j4.ESTIMAND_CONTRAST,
                "outcome_window_id": time_contract["outcome_window_id"],
            },
        },
        "v5_candidate": candidate,
    }


def _project(request: dict) -> dict:
    return j4._compile_comparative_projection(request)


def _replace_fixture_year(value):
    if isinstance(value, dict):
        return {key: _replace_fixture_year(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_fixture_year(item) for item in value]
    if isinstance(value, str) and value.startswith("2025-"):
        return "2020-" + value[5:]
    return deepcopy(value)


def _replace_fixture_identity(value, replacements: dict[str, str]):
    if isinstance(value, dict):
        return {key: _replace_fixture_identity(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_fixture_identity(item, replacements) for item in value]
    if isinstance(value, str):
        return replacements.get(value, value)
    return deepcopy(value)


def _public_context(request: dict) -> tuple[dict, dict, dict, dict, str, sqlite3.Connection]:
    source_by_ref, manifest, _, _, original_inputs = _j2_bound_inputs()
    candidate = request["v5_candidate"]
    action = candidate["action_scope"]
    target_member = next(
        member for member in candidate["cohort_snapshot"]["members"]
        if member["issuer_id"] == action["focal_issuer_id"]
    )
    cutoff_at = candidate["time_contract"]["research_cutoff_at"]
    reconstruction_inputs = _replace_fixture_year(original_inputs)
    reconstruction_inputs = _replace_fixture_identity(reconstruction_inputs, {
        "UNIT:BUSINESS": target_member["responsibility_unit_id"],
        "ARENA:CORE": candidate["competitive_arena"]["competitive_arena_id"],
    })
    receipt = reconstruction_inputs["source_packet_receipt"]
    for item in (
        receipt,
        reconstruction_inputs["spec"],
        reconstruction_inputs["decision_contract"],
    ):
        item["company_id"] = target_member["company_id"]
        item["issuer_id"] = target_member["issuer_id"]
        item["cutoff_at"] = cutoff_at
    for item in (
        reconstruction_inputs["enterprise_model"],
        reconstruction_inputs["decision_ledger"],
    ):
        item["company_id"] = target_member["company_id"]
    reconstruction_inputs["enterprise_model"]["cutoff_at"] = cutoff_at
    package_result = source_packet.compile_core_source_package(receipt)
    assert package_result["valid"], package_result["findings"]
    reconstruction_inputs["source_package"] = package_result["source_package"]
    compiled = j1.compile_enterprise_reconstruction(
        reconstruction_inputs["spec"],
        source_packet_receipt=receipt,
        source_package=reconstruction_inputs["source_package"],
        enterprise_model=reconstruction_inputs["enterprise_model"],
        decision_ledger=reconstruction_inputs["decision_ledger"],
        decision_contract=reconstruction_inputs["decision_contract"],
    )
    assert compiled["valid"], compiled["findings"]
    reconstruction_read_model = compiled["reconstruction"]
    manifest["company_id"] = target_member["company_id"]
    manifest["issuer_id"] = target_member["issuer_id"]
    manifest["cutoff_at"] = cutoff_at
    manifest["outcome_cells"].extend([
        {
            "outcome_cell_id": "CELL:D3",
            "dimension": "OPERATIONS",
            "status": "UNKNOWN",
            "measurement_contract_ref": "METRIC:D3",
            "custodian_receipt_ref": "",
        },
        {
            "outcome_cell_id": "CELL:D4",
            "dimension": "CASH",
            "status": "UNKNOWN",
            "measurement_contract_ref": "METRIC:D4",
            "custodian_receipt_ref": "",
        },
    ])
    primary_episode_thread = manifest["mechanism_threads"][0]
    primary_episode_thread["hypotheses"] = [
        {
            "hypothesis_id": action["h_a"]["hypothesis_id"],
            "role": "H_A",
            "statement": action["h_a"]["mechanism"],
        },
        {
            "hypothesis_id": action["h_b"]["hypothesis_id"],
            "role": "H_B",
            "statement": action["h_b"]["mechanism"],
        },
    ]
    primary_episode_thread["outcome_cell_ids"] = ["CELL:D3", "CELL:D4"]
    source_by_ref = {
        source["source_ref"]: source
        for source in reconstruction_inputs["source_package"]["sources"]
    }

    thread_set = _j2_thread_set(source_by_ref, manifest, reconstruction_read_model)
    for thread in thread_set["threads"]:
        for source_ref in thread["source_refs"]:
            source_ref["available_at"] = "2020-12-30T00:00:00+00:00"

    primary = thread_set["threads"][0]
    primary["claim_type"] = j4.RELATIVE_CAUSAL
    primary["hypotheses"] = deepcopy(primary_episode_thread["hypotheses"])
    primary["responsibility_boundary"] = {
        "responsibility_unit_id": target_member["responsibility_unit_id"],
        "arena_id": candidate["competitive_arena"]["competitive_arena_id"],
    }
    primary["e3_comparative_requested"] = True

    primary["comparative_projection_contract"] = {
        "hypothesis_bindings": [
            {
                "role": role,
                "j2_hypothesis_id": hypothesis["hypothesis_id"],
                "j2_statement": hypothesis["statement"],
                "v5_hypothesis_id": action[key]["hypothesis_id"],
                "v5_mechanism": action[key]["mechanism"],
            }
            for role, key, hypothesis in (
                ("H_A", "h_a", primary["hypotheses"][0]),
                ("H_B", "h_b", primary["hypotheses"][1]),
            )
        ],
        "outcome_bindings": [
            {
                "outcome_cell_id": "CELL:" + contract["clock"],
                "measurement_contract_ref": contract["metric_id"],
                "v5_measurement_contracts": [deepcopy(contract)],
            }
            for contract in candidate["measurement_contracts"]
        ],
        "source_lineage": {
            "j1_source_packet_refs": [deepcopy(reconstruction_read_model["source_packet_ref"])],
            "j2_source_refs": deepcopy(primary["source_refs"]),
            "v5_source_provenance": deepcopy(candidate["source_provenance"]),
            "v5_sources": deepcopy(candidate["source_manifest"]),
        },
    }

    registry = sqlite3.connect(":memory:")
    j1.register_frozen_reconstruction(
        registry,
        reconstruction_read_model,
        reconstruction_inputs,
        frozen_at=datetime.now(timezone.utc).isoformat(),
    )
    return (
        manifest,
        reconstruction_read_model,
        reconstruction_inputs,
        thread_set,
        primary["thread_id"],
        registry,
    )


def _project_public(request: dict) -> dict:
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, thread_id, registry = _public_context(request)
    return j4._compile_serialized_j2_thread_projection_with_registry(
        manifest,
        reconstruction_read_model,
        reconstruction_inputs,
        thread_set,
        thread_id,
        request.get("target_trial_bindings"),
        request.get("v5_candidate"),
        reconstruction_registry=registry,
    )


def test_j4_schema_declares_thread_local_candidate_only_authority() -> None:
    schema = json.loads(
        (
            Path(__file__).parents[1]
            / "schemas"
            / "enterprise_judgment_comparative_projection.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert schema["properties"]["schema_version"]["const"] == j4.SCHEMA_VERSION
    assert schema["properties"]["projection_status"]["enum"] == [
        j4.NOT_REQUESTED,
        j4.NOT_ADMITTED,
        j4.ADMISSION_CANDIDATE,
    ]
    assert schema["$defs"]["locality"]["properties"]["e0_e2_unaffected"]["const"] is True
    authority = schema["$defs"]["authority"]["properties"]
    assert authority["pre_outcome_projection_only"]["const"] is True
    assert all(
        definition["const"] is False
        for name, definition in authority.items()
        if name != "pre_outcome_projection_only"
    )


def test_public_j4_api_accepts_only_a_frozen_j1_identity() -> None:
    assert tuple(inspect.signature(j4.compile_serialized_j2_thread_projection).parameters) == (
        "episode_manifest",
        "reconstruction_ref",
        "mechanism_thread_set",
        "thread_id",
        "target_trial_bindings",
        "v5_candidate",
    )


def test_relative_causal_e3_thread_projects_the_unchanged_admitted_v5_candidate() -> None:
    request = _request()
    before = deepcopy(request)

    result = _project(request)

    assert result["projection_status"] == j4.ADMISSION_CANDIDATE
    assert result["findings"] == []
    assert result["v5_validation"] == {
        "schema_version": v5.SCHEMA_VERSION,
        "method_epoch_id": v5.METHOD_EPOCH_ID,
        "candidate_id": request["v5_candidate"]["candidate_id"],
        "valid": True,
        "admission_status": v5.SELECTION_ADMITTED,
        "findings": [],
    }
    assert result["comparative_candidate"] == request["v5_candidate"]
    assert result["comparative_candidate"] is not request["v5_candidate"]
    assert request == before
    assert result["locality"] == {
        "applies_only_to_thread_id": "THREAD:RELATIVE:NETWORK",
        "e0_e2_unaffected": True,
        "other_threads_unaffected": True,
        "industry_block_unaffected": True,
    }
    assert all(
        value is False
        for key, value in result["authority"].items()
        if key != "pre_outcome_projection_only"
    )


def test_public_j4_compiles_a_complete_relative_causal_j2_thread_before_v5() -> None:
    request = _request()
    result = _project_public(request)

    assert result["projection_status"] == j4.ADMISSION_CANDIDATE
    assert result["comparative_candidate"] == request["v5_candidate"]
    assert result["thread_ref"] == {
        "thread_id": "THREAD:CLAIM:OPERATIONS",
        "claim_class": "RELATIVE_CAUSAL",
        "requested_admission_level": "E3_COMPARATIVE_LAB",
    }
    assert result["locality"]["e0_e2_unaffected"] is True
    assert result["locality"]["other_threads_unaffected"] is True
    assert result["locality"]["industry_block_unaffected"] is True
    assert result["authority"]["cjo_authorized"] is False
    assert result["authority"]["valuation_authorized"] is False
    assert result["authority"]["report_authorized"] is False
    assert result["authority"]["investment_authorized"] is False


@pytest.mark.parametrize("replacement", ["MECHANISM", "MEASUREMENT", "SOURCE"])
def test_public_j4_rejects_a_v5_candidate_that_no_longer_answers_the_j2_question(
    replacement: str,
) -> None:
    request = _request()
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, thread_id, registry = _public_context(request)
    if replacement == "MECHANISM":
        request["v5_candidate"]["action_scope"]["h_a"]["mechanism"] = (
            "A different warehouse automation mechanism drives labor productivity."
        )
        expected = "j2_v5_bridge.hypotheses_must_match_j2_and_v5_semantics"
    elif replacement == "MEASUREMENT":
        request["v5_candidate"]["measurement_contracts"][0]["economic_construct"] = (
            "A_DIFFERENT_OPERATING_CONSTRUCT"
        )
        expected = "j2_v5_bridge.measurement_contracts_must_match_v5_semantics"
    else:
        request["v5_candidate"]["source_manifest"][0]["official_artifact_id"] = (
            "ACTION:DIFFERENT-SOURCE-PACKAGE"
        )
        expected = "j2_v5_bridge.source_lineage_must_match_j1_j2_and_v5"

    result = j4._compile_serialized_j2_thread_projection_with_registry(
        manifest,
        reconstruction_read_model,
        reconstruction_inputs,
        thread_set,
        thread_id,
        request["target_trial_bindings"],
        request["v5_candidate"],
        reconstruction_registry=registry,
    )

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert expected in result["findings"]


def test_public_j4_rejects_a_caller_supplied_bridge_override() -> None:
    request = _request()
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, thread_id, registry = _public_context(request)
    request["target_trial_bindings"]["j2_v5_bridge"] = deepcopy(
        thread_set["threads"][0]["comparative_projection_contract"]
    )

    result = j4._compile_serialized_j2_thread_projection_with_registry(
        manifest,
        reconstruction_read_model,
        reconstruction_inputs,
        thread_set,
        thread_id,
        request["target_trial_bindings"],
        request["v5_candidate"],
        reconstruction_registry=registry,
    )

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert (
        "projection_request.target_trial_bindings_contains_unapproved_field:j2_v5_bridge"
        in result["findings"]
    )


def test_j4_internal_adapter_rejects_a_fully_recompiled_replacement_of_registered_j1() -> None:
    request = _request()
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, thread_id, registry = _public_context(request)
    forged_inputs = deepcopy(reconstruction_inputs)
    forged_ref = {"receipt_id": "SP:FORGED:J4:SYNCHRONIZED", "receipt_version": 1}
    forged_inputs["source_packet_receipt"]["packet_id"] = forged_ref["receipt_id"]
    projected = source_packet.compile_core_source_package(forged_inputs["source_packet_receipt"])
    assert projected["valid"], projected["findings"]
    forged_inputs["source_package"] = projected["source_package"]
    forged_inputs["spec"]["source_packet_ref"] = deepcopy(forged_ref)
    forged_inputs["decision_contract"]["evidence_budget"]["source_packet_refs"] = [
        deepcopy(forged_ref)
    ]
    forged_inputs["enterprise_model"]["source_package_id"] = forged_ref["receipt_id"]
    compiled = j1.compile_enterprise_reconstruction(
        forged_inputs["spec"],
        source_packet_receipt=forged_inputs["source_packet_receipt"],
        source_package=forged_inputs["source_package"],
        enterprise_model=forged_inputs["enterprise_model"],
        decision_ledger=forged_inputs["decision_ledger"],
        decision_contract=forged_inputs["decision_contract"],
    )
    assert compiled["valid"], compiled["findings"]
    thread_set["threads"][0]["comparative_projection_contract"]["source_lineage"][
        "j1_source_packet_refs"
    ] = [deepcopy(forged_ref)]

    result = j4._compile_serialized_j2_thread_projection_with_registry(
        manifest,
        compiled["reconstruction"],
        forged_inputs,
        thread_set,
        thread_id,
        request["target_trial_bindings"],
        request["v5_candidate"],
        reconstruction_registry=registry,
    )

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert any(
        "serialized_j2.j2_compile_failed:reconstruction_registry:" in finding
        for finding in result["findings"]
    )


def test_public_j4_requires_the_canonical_frozen_j1_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, thread_id, _ = _public_context(request)
    monkeypatch.setattr(j1, "CANONICAL_REGISTRY_PATH", tmp_path / "missing-canonical.db")

    result = j4.compile_serialized_j2_thread_projection(
        manifest,
        thread_set["reconstruction_ref"],
        thread_set,
        thread_id,
        request["target_trial_bindings"],
        request["v5_candidate"],
    )

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert result["findings"] == [
        "reconstruction_registry:canonical_frozen_reconstruction_registry_unavailable"
    ]


def test_public_j4_reads_the_preexisting_canonical_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, thread_id, _ = _public_context(request)
    registry_path = tmp_path / "canonical.db"
    registry = sqlite3.connect(registry_path)
    j1.register_frozen_reconstruction(
        registry,
        reconstruction_read_model,
        reconstruction_inputs,
        frozen_at=datetime.now(timezone.utc).isoformat(),
    )
    registry.close()
    monkeypatch.setattr(j1, "CANONICAL_REGISTRY_PATH", registry_path)

    result = j4.compile_serialized_j2_thread_projection(
        manifest,
        thread_set["reconstruction_ref"],
        thread_set,
        thread_id,
        request["target_trial_bindings"],
        request["v5_candidate"],
    )

    assert result["projection_status"] == j4.ADMISSION_CANDIDATE
    assert result["comparative_candidate"] == request["v5_candidate"]


def test_incomplete_handcrafted_j2_cannot_enter_the_public_v5_path() -> None:
    request = _request()
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, thread_id, registry = _public_context(request)
    incomplete = {
        "schema_version": j4.J2_SCHEMA_VERSION,
        "thread_set_id": thread_set["thread_set_id"],
        "episode_ref": deepcopy(thread_set["episode_ref"]),
        "threads": [{"thread_id": thread_id}],
        "outcome_access": "NONE",
    }

    result = j4._compile_serialized_j2_thread_projection_with_registry(
        manifest,
        reconstruction_read_model,
        reconstruction_inputs,
        incomplete,
        thread_id,
        request["target_trial_bindings"],
        request["v5_candidate"],
        reconstruction_registry=registry,
    )

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert any("serialized_j2.j2_compile_failed:" in finding for finding in result["findings"])
    assert result["v5_validation"]["admission_status"] == "NOT_EVALUATED"


def test_unresolved_complete_j2_thread_cannot_bypass_j2_and_enter_v5() -> None:
    request = _request()
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, thread_id, registry = _public_context(request)
    thread_set["threads"][0]["source_refs"][0]["source_ref"] = "SRC:UNKNOWN"
    before = deepcopy((manifest, reconstruction_read_model, thread_set))

    result = j4._compile_serialized_j2_thread_projection_with_registry(
        manifest,
        reconstruction_read_model,
        reconstruction_inputs,
        thread_set,
        thread_id,
        request["target_trial_bindings"],
        request["v5_candidate"],
        reconstruction_registry=registry,
    )

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert "serialized_j2.compiled_thread_view_must_be_resolved" in result["findings"]
    assert "serialized_j2.compiled_thread_view_not_comparative_eligible" in result["findings"]
    assert result["locality"]["e0_e2_unaffected"] is True
    assert result["locality"]["other_threads_unaffected"] is True
    assert result["locality"]["industry_block_unaffected"] is True
    assert (manifest, reconstruction_read_model, thread_set) == before


def test_j4_allows_operating_capital_return_language() -> None:
    request = _request()
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, thread_id, registry = _public_context(request)
    statement = (
        "Capital investment return improves only if utilization and unit economics improve."
    )
    manifest["mechanism_threads"][0]["hypotheses"][0]["statement"] = statement
    thread_set["threads"][0]["hypotheses"][0]["statement"] = statement
    bridge = thread_set["threads"][0]["comparative_projection_contract"]
    bridge["hypothesis_bindings"][0]["j2_statement"] = statement
    bridge["hypothesis_bindings"][0]["v5_mechanism"] = statement
    request["v5_candidate"]["action_scope"]["h_a"]["mechanism"] = statement
    _refresh_reviewed_selection_contract(request["v5_candidate"])

    result = j4._compile_serialized_j2_thread_projection_with_registry(
        manifest,
        reconstruction_read_model,
        reconstruction_inputs,
        thread_set,
        thread_id,
        request["target_trial_bindings"],
        request["v5_candidate"],
        reconstruction_registry=registry,
    )

    assert result["projection_status"] == j4.ADMISSION_CANDIDATE


def test_serialized_j2_nonrelative_thread_does_not_activate_j4() -> None:
    request = _request()
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, thread_id, registry = _public_context(request)
    thread_set["threads"][0]["claim_type"] = "WITHIN_CASE_MECHANISM"
    thread_set["threads"][0]["e3_comparative_requested"] = False

    result = j4._compile_serialized_j2_thread_projection_with_registry(
        manifest,
        reconstruction_read_model,
        reconstruction_inputs,
        thread_set,
        thread_id,
        None,
        None,
        reconstruction_registry=registry,
    )

    assert result["projection_status"] == j4.NOT_REQUESTED
    assert result["comparative_candidate"] is None


@pytest.mark.parametrize("leak_kind", ["RETURN_NARRATIVE", "LATE_SOURCE"])
def test_serialized_j2_normalization_does_not_drop_preoutcome_leakage(leak_kind: str) -> None:
    request = _request()
    manifest, reconstruction_read_model, reconstruction_inputs, thread_set, thread_id, registry = _public_context(request)
    if leak_kind == "RETURN_NARRATIVE":
        manifest["mechanism_threads"][0]["hypotheses"][0]["statement"] = (
            "The later stock return proves H-A."
        )
        thread_set["threads"][0]["hypotheses"][0]["statement"] = (
            "The later stock return proves H-A."
        )
        expected = "pre_outcome_narrative_contains_price_return_or_post_cutoff_leakage"
    else:
        thread_set["threads"][0]["source_refs"][0]["available_at"] = (
            "2021-01-02T00:00:00+00:00"
        )
        expected = "source_must_be_available_at_or_before_cutoff"

    result = j4._compile_serialized_j2_thread_projection_with_registry(
        manifest,
        reconstruction_read_model,
        reconstruction_inputs,
        thread_set,
        thread_id,
        request["target_trial_bindings"],
        request["v5_candidate"],
        reconstruction_registry=registry,
    )

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert any(expected in finding for finding in result["findings"])


@pytest.mark.parametrize(
    ("claim_class", "admission_level"),
    [
        ("MECHANISM_CAUSAL", j4.E3_COMPARATIVE_LAB),
        (j4.RELATIVE_CAUSAL, "E2_MECHANISM_PROBE"),
        ("QUALITATIVE_REFERENCE", "E1_RECONSTRUCTION"),
    ],
)
def test_j4_is_not_requested_without_the_exact_relative_causal_e3_pair(
    claim_class: str, admission_level: str,
) -> None:
    request = _request()
    request["thread_ref"]["claim_class"] = claim_class
    request["thread_ref"]["requested_admission_level"] = admission_level
    request.pop("target_trial_bindings")
    request.pop("v5_candidate")

    result = _project(request)

    assert result["projection_status"] == j4.NOT_REQUESTED
    assert result["comparative_candidate"] is None
    assert result["v5_validation"]["admission_status"] == "NOT_EVALUATED"
    assert result["locality"]["e0_e2_unaffected"] is True
    assert result["locality"]["other_threads_unaffected"] is True
    assert result["locality"]["industry_block_unaffected"] is True


@pytest.mark.parametrize(
    "binding_name",
    [
        "action_exposure",
        "eligibility_time_zero",
        "comparator_roles",
        "outcome_follow_up",
        "censoring_interference",
        "estimand",
    ],
)
def test_each_target_trial_binding_is_required_only_for_the_requested_thread(
    binding_name: str,
) -> None:
    request = _request()
    request["target_trial_bindings"].pop(binding_name)

    result = _project(request)

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert any(binding_name in finding for finding in result["findings"])
    assert result["v5_validation"]["admission_status"] == v5.SELECTION_ADMITTED
    assert result["locality"]["applies_only_to_thread_id"] == request["thread_ref"]["thread_id"]
    assert result["locality"]["e0_e2_unaffected"] is True
    assert result["locality"]["other_threads_unaffected"] is True
    assert result["locality"]["industry_block_unaffected"] is True


def test_binding_drift_cannot_borrow_action_or_estimand_from_another_thread() -> None:
    request = _request()
    request["target_trial_bindings"]["action_exposure"]["action_id"] = "ACTION:OTHER-THREAD"
    request["target_trial_bindings"]["estimand"]["action_id"] = "ACTION:OTHER-THREAD"
    request["thread_ref"]["responsibility_boundary"]["arena_id"] = "ARENA:OTHER-THREAD"

    result = _project(request)

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert "projection_request.action_exposure_must_match_v5_candidate" in result["findings"]
    assert "projection_request.estimand_must_match_v5_candidate" in result["findings"]
    assert (
        "projection_request.thread_ref.responsibility_boundary_must_match_v5_target_and_arena"
        in result["findings"]
    )
    assert result["v5_validation"]["admission_status"] == v5.SELECTION_ADMITTED


@pytest.mark.parametrize("reference_field", ["relative_reference_id", "archetype_id"])
def test_relative_references_and_archetypes_cannot_masquerade_as_untreated_controls(
    reference_field: str,
) -> None:
    request = _request()
    request["v5_candidate"]["counterfactual_panel"]["members"][0][reference_field] = "REF:INDUSTRY"

    result = _project(request)

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert result["v5_validation"]["admission_status"] == "NOT_EVALUATED"
    assert any(
        "relative_reference_or_archetype_cannot_be_comparator" in finding
        for finding in result["findings"]
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("market_price", 12.5),
        ("investment_return", 0.18),
        ("post_cutoff_data", {"observed": "later result"}),
        ("actual_value", 100.0),
    ],
)
def test_preoutcome_payload_rejects_price_return_and_postcutoff_actual_data(
    field: str, value: object,
) -> None:
    request = _request()
    request["v5_candidate"][field] = value

    result = _project(request)

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert result["v5_validation"]["admission_status"] == "NOT_EVALUATED"
    assert any("pre_outcome_price_return_or_actual_data_forbidden" in item for item in result["findings"])


def test_preoutcome_payload_rejects_return_leakage_inside_v5_hypothesis_text() -> None:
    request = _request()
    request["v5_candidate"]["action_scope"]["h_a"]["mechanism"] = (
        "The later stock return proves the operating mechanism."
    )

    result = _project(request)

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert result["v5_validation"]["admission_status"] == "NOT_EVALUATED"
    assert any("pre_outcome_narrative_leakage_forbidden" in item for item in result["findings"])


def test_postcutoff_source_remains_a_v5_rejection_not_a_j4_reinterpretation() -> None:
    request = _request()
    request["v5_candidate"]["source_manifest"][0]["published_at_or_date"] = "2022-01-01"
    _refresh_reviewed_selection_contract(request["v5_candidate"])

    result = _project(request)

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["v5_validation"]["admission_status"] == v5.NO_PRIMARY
    assert "source_not_cutoff_before" in result["v5_validation"]["findings"]
    assert "v5:source_not_cutoff_before" in result["findings"]


def test_invalid_v5_panel_role_is_not_recruited_or_repaired_by_j4() -> None:
    request = _request()
    before_members = deepcopy(request["v5_candidate"]["counterfactual_panel"]["members"])
    request["v5_candidate"]["counterfactual_panel"]["members"][0]["causal_role"] = "RELATIVE_REFERENCE"
    _refresh_reviewed_selection_contract(request["v5_candidate"])

    result = _project(request)

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert result["authority"]["peer_recruitment_authorized"] is False
    assert len(request["v5_candidate"]["counterfactual_panel"]["members"]) == len(before_members)
    assert request["v5_candidate"]["counterfactual_panel"]["members"][0]["causal_role"] == "RELATIVE_REFERENCE"


def test_missing_h2_provenance_is_not_fabricated() -> None:
    request = _request()
    request["v5_candidate"]["source_provenance"].pop("h2")
    _refresh_reviewed_selection_contract(request["v5_candidate"])

    result = _project(request)

    assert result["projection_status"] == j4.NOT_ADMITTED
    assert result["comparative_candidate"] is None
    assert result["v5_validation"]["admission_status"] == v5.NOT_ADMITTED
    assert result["authority"]["h2_fabrication_authorized"] is False
    assert "h2" not in request["v5_candidate"]["source_provenance"]
