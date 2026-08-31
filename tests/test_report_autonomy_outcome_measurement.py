from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.report_autonomy_appliance_cohort_prereg_generator import (
    build_appliance_cohort_preregistration,
)
from scripts.report_autonomy_outcome_measurement import (
    build_anonymous_arm_claim_manifest,
    build_anonymous_case_claim_binding_receipt,
    build_anonymous_outcome_assessment,
    build_case_contract,
    materialize_case_contracts,
    validate_anonymous_arm_claim_manifest,
    validate_anonymous_case_claim_binding_receipt,
    validate_anonymous_outcome_assessment,
    validate_case_contract,
    validate_outcome_field_receipts,
    validate_outcome_measurement_plane,
)


_ROOT = Path(__file__).resolve().parents[1]
_INPUT = _ROOT / "tests/fixtures/report_autonomy_appliance_cohort_prereg_input.json"


def _preregistration_with_temporary_measurement_refs() -> dict[str, object]:
    preregistration = build_appliance_cohort_preregistration(
        json.loads(_INPUT.read_text(encoding="utf-8"))
    )
    for measurement in preregistration["outcome_measurements"]:
        measurement["measurement_contract_ref"] = (
            "measurements/" + measurement["case_id"].replace(":", "_") + ".json"
        )
    return preregistration


def test_plane_refuses_dangling_measurement_contract_references(tmp_path: Path) -> None:
    preregistration = _preregistration_with_temporary_measurement_refs()

    result = validate_outcome_measurement_plane(preregistration, project_root=tmp_path)

    assert result["state"] == "INVALID"
    assert any("measurement_contract_missing" in item for item in result["findings"])


def test_materialized_eight_contracts_are_value_free_and_reviewable(tmp_path: Path) -> None:
    preregistration = _preregistration_with_temporary_measurement_refs()

    result = materialize_case_contracts(preregistration, project_root=tmp_path)

    assert result["state"] == "REVIEWABLE"
    paths = [
        tmp_path / measurement["measurement_contract_ref"]
        for measurement in preregistration["outcome_measurements"]
    ]
    assert len(paths) == 8 and all(path.is_file() for path in paths)
    first = json.loads(paths[0].read_text(encoding="utf-8"))
    assert first["state"] == "PREOUTCOME_FROZEN"
    assert first["custody"]["outcome_access"] == "SEALED"
    assert first["assessment_anchors"][0]["assessment_mode"] == "NOT_MEASURABLE_BY_DESIGN"
    assert all("observed_value" not in json.dumps(contract, ensure_ascii=False) for contract in [first])


def test_contract_rejects_parent_substitution_and_maintenance_capex_invention() -> None:
    preregistration = _preregistration_with_temporary_measurement_refs()
    case_id = preregistration["cases"][0]["case_id"]
    contract = build_case_contract(preregistration, case_id)
    invalid = deepcopy(contract)
    invalid["measurement_fields"][0]["boundary_id"] = "BOUNDARY:PARENT_ONLY"
    invalid["assessment_anchors"][2]["limitations"] = "Total capex is maintenance capital."

    result = validate_case_contract(invalid, preregistration=preregistration, case_id=case_id)

    assert result["state"] == "INVALID"
    assert "contract.measurement_fields[0].boundary_invalid" in result["findings"]
    assert "contract.not_exact_frozen_case_template" in result["findings"]


def test_contract_rejects_an_unspecified_predicate_direction_disposition() -> None:
    preregistration = _preregistration_with_temporary_measurement_refs()
    case_id = preregistration["cases"][0]["case_id"]
    invalid = build_case_contract(preregistration, case_id)
    invalid["assessment_anchors"][1]["predicate_disposition"]["rules"].pop()

    result = validate_case_contract(invalid, preregistration=preregistration, case_id=case_id)

    assert result["state"] == "INVALID"
    assert any("predicate_disposition_must_cover_each_predicate_and_direction" in item for item in result["findings"])


def test_plane_rejects_a_contract_reference_that_escapes_project_root(tmp_path: Path) -> None:
    preregistration = _preregistration_with_temporary_measurement_refs()
    preregistration["outcome_measurements"][0]["measurement_contract_ref"] = "../escape.json"

    result = validate_outcome_measurement_plane(preregistration, project_root=tmp_path)

    assert result["state"] == "INVALID"
    assert any("measurement_contract_ref_escapes_project_root" in item for item in result["findings"])


def _episode_for_contract(contract: dict[str, object]) -> dict[str, object]:
    identity = contract["identity"]
    return {
        "company_id": identity["company_id"],
        "cutoff_at": identity["cutoff_at"],
        "underwriting_thesis": {
            "economic_directions": {
                "normal_earnings": "IMPROVES",
                "owner_cash": "DETERIORATES",
                "permanent_loss": "DETERIORATES",
            },
        },
    }


def _observed_receipts(contract: dict[str, object]) -> dict[str, object]:
    values: dict[str, float] = {}
    for field in contract["measurement_fields"]:
        field_id = field["field_id"]
        values[field_id] = 10.0
        if "SHORT_TERM_DEBT:P3" in field_id or "LONG_TERM_DEBT:P3" in field_id:
            values[field_id] = 20.0
    return {
        "schema_version": "report-autonomy-outcome-field-receipts.v1",
        "state": "OUTCOME_FIELD_RECEIPTS_FROZEN",
        "contract_id": contract["contract_id"],
        "case_id": contract["identity"]["case_id"],
        "field_receipts": [
            {
                "receipt_id": "RECEIPT:" + field["field_id"],
                "field_id": field["field_id"],
                "status": "OBSERVED",
                "observed_value": values[field["field_id"]],
                "unit": field["unit"],
                "source_period_slot": field["period_slot"],
                "source_locator": "synthetic official annual-report locator",
            }
            for field in contract["measurement_fields"]
        ],
    }


def test_anonymous_claim_manifest_and_assessment_are_exactly_contract_bound() -> None:
    preregistration = _preregistration_with_temporary_measurement_refs()
    case_id = preregistration["cases"][0]["case_id"]
    contract = build_case_contract(preregistration, case_id)
    episode = _episode_for_contract(contract)
    manifest = build_anonymous_arm_claim_manifest(
        contract,
        episode=episode,
        anonymous_label="ANON_BCDFGHJKLMNP",
        frozen_episode_ref="anonymous/ANON_BCDFGHJKLMNP/episode.json",
    )
    additional_manifests = [
        build_anonymous_arm_claim_manifest(
            contract,
            episode=episode,
            anonymous_label=label,
            frozen_episode_ref="anonymous/" + label + "/episode.json",
        )
        for label in ("ANON_BCDFGHJKLMPQ", "ANON_BCDFGHJKLMQR", "ANON_BCDFGHJKLMQS")
    ]
    pairs = [(manifest, episode)] + [(item, episode) for item in additional_manifests]
    binding = build_anonymous_case_claim_binding_receipt(
        contract,
        manifest_episode_pairs=pairs,
    )
    receipts = _observed_receipts(contract)

    assert validate_anonymous_arm_claim_manifest(
        manifest, contract=contract, episode=episode,
    )["state"] == "REVIEWABLE"
    assert validate_outcome_field_receipts(receipts, contract=contract)["state"] == "REVIEWABLE"
    assert validate_anonymous_case_claim_binding_receipt(
        binding,
        contract=contract,
        manifest_episode_pairs=pairs,
    )["state"] == "REVIEWABLE"
    assessment = build_anonymous_outcome_assessment(
        manifest, contract=contract, field_receipts=receipts, claim_binding_receipt=binding,
        manifest_episode_pairs=pairs,
    )
    assert validate_anonymous_outcome_assessment(
        assessment, manifest=manifest, contract=contract, field_receipts=receipts, claim_binding_receipt=binding,
        manifest_episode_pairs=pairs,
    )["state"] == "REVIEWABLE"
    statuses = {item["claim_id"]: item["assessment_status"] for item in assessment["assessments"]}
    assert statuses["CLAIM:NORMAL_EARNINGS"] == "SUPPORTED"
    assert statuses["CLAIM:OWNER_CASH"] == "WEAKENED_OR_FALSIFIED"
    assert statuses["CLAIM:PERMANENT_LOSS"] == "SUPPORTED"
    assert statuses["CLAIM:INDUSTRY_SITUATION"] == "NON_DISCRIMINATING"


def test_manifest_or_assessor_cannot_change_direction_or_predicate_result() -> None:
    preregistration = _preregistration_with_temporary_measurement_refs()
    case_id = preregistration["cases"][0]["case_id"]
    contract = build_case_contract(preregistration, case_id)
    episode = _episode_for_contract(contract)
    manifest = build_anonymous_arm_claim_manifest(
        contract, episode=episode, anonymous_label="ANON_BCDFGHJKLMNP", frozen_episode_ref="episode.json",
    )
    receipts = _observed_receipts(contract)
    additional_manifests = [
        build_anonymous_arm_claim_manifest(
            contract, episode=episode, anonymous_label=label, frozen_episode_ref="episode.json",
        )
        for label in ("ANON_BCDFGHJKLMQP", "ANON_BCDFGHJKLMQR", "ANON_BCDFGHJKLMQS")
    ]
    pairs = [(manifest, episode)] + [(item, episode) for item in additional_manifests]
    binding = build_anonymous_case_claim_binding_receipt(
        contract,
        manifest_episode_pairs=pairs,
    )
    invalid_manifest = deepcopy(manifest)
    invalid_manifest["claims"][1]["expected_direction"] = "DETERIORATES"
    assert validate_anonymous_arm_claim_manifest(
        invalid_manifest, contract=contract, episode=episode,
    )["state"] == "INVALID"

    assessment = build_anonymous_outcome_assessment(
        manifest, contract=contract, field_receipts=receipts, claim_binding_receipt=binding,
        manifest_episode_pairs=pairs,
    )
    invalid_assessment = deepcopy(assessment)
    invalid_assessment["assessments"][1]["assessment_status"] = "WEAKENED_OR_FALSIFIED"
    assert validate_anonymous_outcome_assessment(
        invalid_assessment, manifest=manifest, contract=contract, field_receipts=receipts, claim_binding_receipt=binding,
        manifest_episode_pairs=pairs,
    )["state"] == "INVALID"

    with pytest.raises(ValueError, match="claim_binding_receipt_invalid"):
        build_anonymous_outcome_assessment(
            invalid_manifest, contract=contract, field_receipts=receipts, claim_binding_receipt=binding,
            manifest_episode_pairs=[(invalid_manifest, episode)] + [(item, episode) for item in additional_manifests],
        )

    coordinated_binding = deepcopy(binding)
    coordinated_binding["claim_bindings"][0]["claims"][1]["expected_direction"] = "DETERIORATES"
    with pytest.raises(ValueError, match="claim_binding_receipt_invalid"):
        build_anonymous_outcome_assessment(
            invalid_manifest, contract=contract, field_receipts=receipts,
            claim_binding_receipt=coordinated_binding,
            manifest_episode_pairs=[(invalid_manifest, episode)] + [(item, episode) for item in additional_manifests],
        )
