from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.historical_role_isolation import (
    METHOD_PACK_SCHEMA_VERSION,
    SCHEMA_VERSION,
    build_forecaster_packet,
    build_holdout_pair_packets,
    build_transfer_forecaster_packet,
    build_selector_packet,
    role_is_contaminated,
    validate_method_pack,
    validate_selector_universe,
    validate_manifest,
)


@pytest.fixture(autouse=True)
def _declared_test_pdfs_are_readable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.historical_role_isolation._pdf_has_extractable_text", lambda _path: True
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


def _method_pack() -> dict:
    return {
        "schema_version": METHOD_PACK_SCHEMA_VERSION,
        "method_pack_id": "METHOD_PACK:JUDGMENT_FIRST:BLIND_FEEDBACK:V1",
        "method_version": "judgment-first-blind-feedback.v1",
        "state": "FROZEN_FOR_HOLDOUT_EVALUATION",
        "frozen_at": "2026-08-28T12:00:00+08:00",
        "rules": [
            {
                "rule_id": "SAME_BOUNDARY_RECURRING_ECONOMICS_FIRST",
                "status": "CANDIDATE_BEHAVIOR_NOT_VALIDATED",
                "scope": "management execution, normal earnings, and valuation direction",
                "trigger": "scale or volume growth is offered as evidence for an upgrade",
                "required_behavior": "build a responsibility-matched recurring-profit or unit-economics bridge first",
                "prohibited_inference": "deployment or scale growth alone proves economic absorption",
                "disconfirming_observation": "matched economics later support the upgrade even though the bridge looked weak",
            }
        ],
        "authority": "RESEARCH_METHOD_ONLY",
        "permissions": {
            "method_validation": "NONE",
            "transfer_validation": "NONE",
            "cjo": "NONE",
            "formal_valuation": "NONE",
            "buy_band": "NONE",
            "report": "NONE",
            "investment_action": "NONE",
        },
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
    contract = packet["judgment_first_contract"]
    assert contract["required_product"]["most_important_enterprise_judgments"]["count"] == 3
    assert "UNKNOWN不是投资处理" in contract["required_product"]["material_treatment_snapshot"]["rule"]
    assert any("ADVERSE" in rule and "ELSE" in rule for rule in contract["outcome_cell_rules"])
    assert any("METHOD_LEARNING_UTILITY" in rule for rule in contract["postoutcome_rules"])
    assert any("GROUP_CASH_PROXY" in rule for rule in contract["economic_bridge_rules"])
    assert any("收入和毛利率不能单独" in rule for rule in contract["economic_bridge_rules"])
    assert "缺少价格本身不能" in contract["required_product"]["material_treatment_snapshot"][
        "valuation_direction_rule"
    ]


def test_holdout_pair_supplies_frozen_method_only_to_enhanced_arm(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["holdout_pair_roles"] = {
        "baseline_forecaster_id": "AGENT:HOLDOUT:BASELINE:FRESH",
        "enhanced_forecaster_id": "AGENT:HOLDOUT:ENHANCED:FRESH",
    }
    method_path = tmp_path / "method-pack.json"
    method_path.write_text(json.dumps(_method_pack()), encoding="utf-8")

    pair = build_holdout_pair_packets(manifest, method_path, tmp_path / "holdout-pair")
    baseline_dir = tmp_path / "holdout-pair" / "baseline"
    enhanced_dir = tmp_path / "holdout-pair" / "enhanced"
    baseline = json.loads((baseline_dir / "FORECASTER_PACKET.json").read_text(encoding="utf-8"))
    enhanced = json.loads((enhanced_dir / "FORECASTER_PACKET.json").read_text(encoding="utf-8"))

    assert baseline["source_budget"] == enhanced["source_budget"] == pair["shared_source_budget"]
    assert baseline["judgment_first_contract"] == enhanced["judgment_first_contract"]
    assert baseline["method_input"] == {"state": "NONE"}
    assert enhanced["method_input"]["state"] == "FROZEN_GENERALIZED_METHOD_SUPPLIED"
    assert not (baseline_dir / "FROZEN_METHOD_PACK.json").exists()
    assert (enhanced_dir / "FROZEN_METHOD_PACK.json").exists()
    assert baseline["outcome_state"] == enhanced["outcome_state"] == "SEALED_NOT_IN_PACKET"


def test_transfer_packet_supplies_frozen_method_without_outcome(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    method_path = tmp_path / "method-pack.json"
    method_path.write_text(json.dumps(_method_pack()), encoding="utf-8")

    packet = build_transfer_forecaster_packet(
        manifest, method_path, tmp_path / "transfer"
    )

    assert packet["evaluation_arm"] == "FROZEN_METHOD_TRANSFER"
    assert packet["method_input"]["state"] == "FROZEN_GENERALIZED_METHOD_SUPPLIED"
    assert (tmp_path / "transfer" / "FROZEN_METHOD_PACK.json").exists()
    assert packet["outcome_state"] == "SEALED_NOT_IN_PACKET"
    rendered = (tmp_path / "transfer" / "FORECASTER_PACKET.json").read_text(
        encoding="utf-8"
    )
    assert "fy2023_outcome" not in rendered.lower()


def test_holdout_pair_rejects_unfrozen_method_or_exposed_arm(tmp_path: Path) -> None:
    invalid_pack = _method_pack()
    invalid_pack["permissions"]["method_validation"] = "VALIDATED"
    invalid_pack["company_id"] = "CN:600161"
    findings = validate_method_pack(invalid_pack)
    assert "method_pack.unapproved_fields:company_id" in findings
    assert "method_pack.permissions_must_all_be_none" in findings

    manifest = _manifest(tmp_path)
    manifest["holdout_pair_roles"] = {
        "baseline_forecaster_id": "AGENT:HOLDOUT:BASELINE:FRESH",
        "enhanced_forecaster_id": "AGENT:HOLDOUT:ENHANCED:FRESH",
    }
    manifest["exposure_ledger"].append({
        "role_id": "AGENT:HOLDOUT:ENHANCED:FRESH",
        "company_id": "HK:00941",
        "access": "DERIVED_CONTENT_READ",
        "source_available_at": "2024-03-21T00:00:00+08:00",
    })
    method_path = tmp_path / "method-pack.json"
    method_path.write_text(json.dumps(_method_pack()), encoding="utf-8")
    with pytest.raises(ValueError, match="enhanced_forecaster_outcome_contaminated"):
        build_holdout_pair_packets(manifest, method_path, tmp_path / "holdout-pair")


def test_checked_in_method_pack_is_generalized_and_unvalidated() -> None:
    repo = Path(__file__).resolve().parents[1]
    path = repo / (
        "docs/development/research/training_campaigns/"
        "JUDGMENT_UTILITY_HISTORICAL_20260828/37_FROZEN_TRAINING_METHOD_PACK_V1.json"
    )
    method_pack = json.loads(path.read_text(encoding="utf-8"))
    assert validate_method_pack(method_pack) == []
    assert all(value == "NONE" for value in method_pack["permissions"].values())
    assert set(method_pack) == {
        "schema_version",
        "method_pack_id",
        "method_version",
        "state",
        "frozen_at",
        "rules",
        "authority",
        "permissions",
    }


def test_post_cutoff_source_and_outcome_locator_are_rejected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    manifest["preoutcome_sources"][0]["available_at"] = "2024-01-01T00:00:00+08:00"
    manifest["sealed_outcome"]["path"] = "/some/outcome.pdf"
    findings = validate_manifest(manifest)
    assert "role_isolation.preoutcome_sources[0].available_after_cutoff" in findings
    assert "role_isolation.outcome_locator_or_value_exposed" in findings


def test_unextractable_pdf_is_rejected_before_forecaster_receives_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _manifest(tmp_path)
    monkeypatch.setattr(
        "scripts.historical_role_isolation._pdf_has_extractable_text", lambda _path: False
    )
    findings = validate_manifest(manifest)
    assert "role_isolation.preoutcome_sources[0].pdf_text_not_extractable" in findings
    with pytest.raises(ValueError, match="pdf_text_not_extractable"):
        build_forecaster_packet(manifest, tmp_path / "unreadable-packet")


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
