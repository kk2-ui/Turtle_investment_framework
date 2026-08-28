from copy import deepcopy
from pathlib import Path

import pytest

from scripts.historical_role_isolation import (
    SCHEMA_VERSION,
    build_forecaster_packet,
    build_selector_packet,
    role_is_contaminated,
    validate_selector_universe,
    validate_manifest,
)


def _manifest(tmp_path: Path) -> dict:
    first = tmp_path / "fy2021.pdf"
    second = tmp_path / "fy2022.pdf"
    first.write_bytes(b"cutoff-safe annual report 2021")
    second.write_bytes(b"cutoff-safe annual report 2022")
    return {
        "schema_version": SCHEMA_VERSION,
        "episode_id": "HIST:HK00941:20230501",
        "company_id": "HK:00941",
        "cutoff_at": "2023-05-01T00:00:00+08:00",
        "roles": {
            "selector_id": "AGENT:SELECTOR:FRESH",
            "forecaster_id": "AGENT:FORECASTER:FRESH",
            "custodian_id": "AGENT:CUSTODIAN:FRESH",
            "reviewer_id": "AGENT:REVIEWER:FRESH",
        },
        "preoutcome_sources": [
            {
                "source_id": "IR:HK00941:FY2021",
                "path": str(first),
                "packet_name": "FY2021.pdf",
                "available_at": "2022-04-01T00:00:00+08:00",
                "time_role": "PRE_CUTOFF",
            },
            {
                "source_id": "IR:HK00941:FY2022",
                "path": str(second),
                "packet_name": "FY2022.pdf",
                "available_at": "2023-03-24T00:00:00+08:00",
                "time_role": "PRE_CUTOFF",
            },
        ],
        "sealed_outcome": {
            "period": "FY2023",
            "existence_confirmed": True,
            "body_access": "CUSTODIAN_ONLY_AFTER_FREEZE",
            "forecaster_visibility": "EXISTENCE_METADATA_ONLY",
        },
        "exposure_ledger": [],
    }


def test_workspace_outcome_presence_is_not_role_exposure(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    (tmp_path / "fy2023_outcome.pdf").write_bytes(b"outcome exists elsewhere")
    assert validate_manifest(manifest) == []
    assert not role_is_contaminated(manifest, "forecaster_id")


def test_metadata_only_outcome_existence_does_not_contaminate(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["exposure_ledger"].append(
        {
            "role_id": "AGENT:FORECASTER:FRESH",
            "company_id": "HK:00941",
            "access": "METADATA_ONLY",
            "source_available_at": "2024-03-21T00:00:00+08:00",
        }
    )
    assert validate_manifest(manifest) == []


@pytest.mark.parametrize("role_key", ["selector_id", "forecaster_id"])
def test_outcome_body_exposure_contaminates_only_exposed_research_role(
    tmp_path: Path, role_key: str
) -> None:
    manifest = _manifest(tmp_path)
    manifest["exposure_ledger"].append(
        {
            "role_id": manifest["roles"][role_key],
            "company_id": "HK:00941",
            "access": "BODY_READ",
            "source_available_at": "2024-03-21T00:00:00+08:00",
        }
    )
    findings = validate_manifest(manifest)
    assert f"role_isolation.{role_key.removesuffix('_id')}_outcome_contaminated" in findings


def test_forecaster_packet_contains_only_allowlisted_preoutcome_inputs(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    output_dir = tmp_path / "packet"
    packet = build_forecaster_packet(manifest, output_dir)
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "FORECASTER_PACKET.json",
        "FY2021.pdf",
        "FY2022.pdf",
    ]
    assert packet["outcome_state"] == "SEALED_NOT_IN_PACKET"
    rendered = (output_dir / "FORECASTER_PACKET.json").read_text(encoding="utf-8")
    assert "fy2023" not in rendered.lower()
    assert "custodian" not in rendered.lower()
    assert "exposure_ledger" not in rendered


def test_post_cutoff_source_and_outcome_locator_are_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["preoutcome_sources"][0]["available_at"] = "2024-01-01T00:00:00+08:00"
    manifest["sealed_outcome"]["path"] = "/some/outcome.pdf"
    findings = validate_manifest(manifest)
    assert "role_isolation.preoutcome_sources[0].available_after_cutoff" in findings
    assert "role_isolation.outcome_locator_or_value_exposed" in findings


def test_role_collision_and_nonempty_output_are_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["roles"]["reviewer_id"] = manifest["roles"]["forecaster_id"]
    assert "role_isolation.roles_must_be_distinct" in validate_manifest(manifest)

    manifest = _manifest(tmp_path)
    output_dir = tmp_path / "packet"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("preserve me", encoding="utf-8")
    with pytest.raises(ValueError, match="output_directory_must_be_empty"):
        build_forecaster_packet(manifest, output_dir)


def test_unrelated_company_exposure_does_not_poison_candidate(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    exposed = deepcopy(manifest)
    exposed["exposure_ledger"].append(
        {
            "role_id": exposed["roles"]["forecaster_id"],
            "company_id": "CN:600104",
            "access": "BODY_READ",
            "source_available_at": "2024-03-21T00:00:00+08:00",
        }
    )
    assert validate_manifest(exposed) == []


def test_same_company_pre_cutoff_body_is_valid_training_input(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["exposure_ledger"].append(
        {
            "role_id": manifest["roles"]["forecaster_id"],
            "company_id": "HK:00941",
            "access": "BODY_READ",
            "source_available_at": "2022-04-01T00:00:00+08:00",
        }
    )
    assert validate_manifest(manifest) == []


@pytest.mark.parametrize("access", ["DERIVED_CONTENT_READ", "PRICE_READ", "RETURN_READ"])
def test_post_cutoff_derived_price_and_return_exposure_contaminate(
    tmp_path: Path, access: str
) -> None:
    manifest = _manifest(tmp_path)
    manifest["exposure_ledger"].append(
        {
            "role_id": manifest["roles"]["forecaster_id"],
            "company_id": "HK:00941",
            "access": access,
            "source_available_at": "2024-03-21T00:00:00+08:00",
        }
    )
    assert "role_isolation.forecaster_outcome_contaminated" in validate_manifest(manifest)


def test_malformed_exposure_is_invalid_instead_of_assumed_safe(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["exposure_ledger"].append(
        {
            "role_id": manifest["roles"]["forecaster_id"],
            "access": "BODY_READ",
        }
    )
    findings = validate_manifest(manifest)
    assert "role_isolation.exposure_ledger[0].company_id_missing" in findings
    assert "role_isolation.exposure_ledger[0].source_available_at_missing" in findings
    assert "role_isolation.exposure_ledger[0].source_available_at_invalid" in findings


def test_selector_packet_exposes_only_preoutcome_metadata(tmp_path: Path) -> None:
    universe = {
        "schema_version": "historical-selector-universe.v1",
        "selector_id": "AGENT:SELECTOR:FRESH",
        "selection_policy": "BUSINESS_MODEL_HETEROGENEITY_THEN_CUTOFF_SOURCE_READINESS",
        "candidates": [
            {
                "company_id": "HK:00941",
                "cutoff_at": "2023-05-01T00:00:00+08:00",
                "business_model_archetype": "TELECOM_NETWORK",
                "preoutcome_source_count": 2,
                "outcome_existence_confirmed": True,
            },
            {
                "company_id": "CN:600104",
                "cutoff_at": "2023-05-01T00:00:00+08:00",
                "business_model_archetype": "AUTO_MANUFACTURING",
                "preoutcome_source_count": 2,
                "outcome_existence_confirmed": True,
            },
        ],
    }
    packet = build_selector_packet(universe, tmp_path / "selector")
    assert len(packet["candidates"]) == 2
    rendered = (tmp_path / "selector" / "SELECTOR_PACKET.json").read_text(encoding="utf-8")
    assert "outcome_locator" not in rendered
    assert "outcome_value" not in rendered


def test_selector_universe_rejects_outcome_or_utility_fields() -> None:
    universe = {
        "schema_version": "historical-selector-universe.v1",
        "selector_id": "AGENT:SELECTOR:FRESH",
        "candidates": [
            {
                "company_id": "HK:00941",
                "cutoff_at": "2023-05-01T00:00:00+08:00",
                "business_model_archetype": "TELECOM_NETWORK",
                "preoutcome_source_count": 2,
                "outcome_existence_confirmed": True,
                "expected_utility": "HIGH",
            }
        ],
    }
    assert any(
        finding.startswith("selector_universe.candidates[0].unapproved_fields:")
        for finding in validate_selector_universe(universe)
    )


@pytest.mark.parametrize("extra_field", ["settlement_verdict", "outcome_summary"])
def test_selector_universe_is_closed_to_result_bearing_aliases(extra_field: str) -> None:
    universe = {
        "schema_version": "historical-selector-universe.v1",
        "selector_id": "AGENT:SELECTOR:FRESH",
        "selection_policy": "BUSINESS_MODEL_HETEROGENEITY_THEN_CUTOFF_SOURCE_READINESS",
        "candidates": [
            {
                "company_id": "HK:00941",
                "cutoff_at": "2023-05-01T00:00:00+08:00",
                "business_model_archetype": "TELECOM_NETWORK",
                "preoutcome_source_count": 2,
                "outcome_existence_confirmed": True,
                extra_field: "result-bearing text",
            }
        ],
    }
    assert any("unapproved_fields" in finding for finding in validate_selector_universe(universe))


def test_selector_policy_is_closed_enum() -> None:
    universe = {
        "schema_version": "historical-selector-universe.v1",
        "selector_id": "AGENT:SELECTOR:FRESH",
        "selection_policy": "CHOOSE HK00941 BECAUSE FY2023 COLLAPSED",
        "candidates": [
            {
                "company_id": "HK:00941",
                "cutoff_at": "2023-05-01T00:00:00+08:00",
                "business_model_archetype": "TELECOM_NETWORK",
                "preoutcome_source_count": 2,
                "outcome_existence_confirmed": True,
            }
        ],
    }
    assert "selector_universe.selection_policy_invalid" in validate_selector_universe(universe)


def test_same_company_different_cutoffs_are_distinct_episodes() -> None:
    candidate = {
        "company_id": "HK:00941",
        "cutoff_at": "2023-05-01T00:00:00+08:00",
        "business_model_archetype": "TELECOM_NETWORK",
        "preoutcome_source_count": 2,
        "outcome_existence_confirmed": True,
    }
    universe = {
        "schema_version": "historical-selector-universe.v1",
        "selector_id": "AGENT:SELECTOR:FRESH",
        "selection_policy": "BUSINESS_MODEL_HETEROGENEITY_THEN_CUTOFF_SOURCE_READINESS",
        "candidates": [candidate, {**candidate, "cutoff_at": "2024-05-01T00:00:00+08:00"}],
    }
    assert validate_selector_universe(universe) == []
    universe["candidates"][1]["cutoff_at"] = candidate["cutoff_at"]
    assert any("company_cutoff_missing_or_duplicate" in f for f in validate_selector_universe(universe))
