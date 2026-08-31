from __future__ import annotations

from copy import deepcopy

from scripts.report_autonomy_cohort_exposure_ledger import (
    SCHEMA_VERSION,
    validate_cohort_exposure_ledger,
)


def _issuer(
    issuer_id: str,
    *,
    entity: str,
    security: str,
    name: str,
    side: str,
    aliases: list[str] | None = None,
) -> dict[str, object]:
    return {
        "issuer_id": issuer_id,
        "legal_entity_id": entity,
        "issuer_name": name,
        "security_identifiers": [security],
        "aliases": aliases or [],
        "intended_side": side,
        "intended_side_reason": "Synthetic pre-selection fixture only.",
    }


def _ledger() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ledger_id": "EXPOSURE:LEDGER:SYNTHETIC:V1",
        "state": "PRE_SELECTION",
        "scope": {
            "industry_scope": "INDUSTRY:SYNTHETIC:CONSUMER_DURABLES",
            "cutoff_at": "2018-12-31T23:59:59+08:00",
            "data_policy": "LOCAL_ONLY_NO_OUTCOME_OR_PRICE",
        },
        "issuer_identities": [
            _issuer(
                "ISSUER:SYNTHETIC:PACK",
                entity="ENTITY:SYNTHETIC:PACK",
                security="SYN:000001",
                name="Synthetic Pack Issuer",
                side="PACK_BUILDING",
            ),
            _issuer(
                "ISSUER:SYNTHETIC:TEACHER",
                entity="ENTITY:SYNTHETIC:TEACHER",
                security="SYN:000002",
                name="Synthetic Teacher Issuer",
                side="EXCLUDED",
                aliases=["Synthetic Teacher Legacy"],
            ),
            _issuer(
                "ISSUER:SYNTHETIC:TEST",
                entity="ENTITY:SYNTHETIC:TEST",
                security="SYN:000003",
                name="Synthetic Test Issuer",
                side="TEST_ACQUISITION",
            ),
            _issuer(
                "ISSUER:SYNTHETIC:DISCOVERY",
                entity="ENTITY:SYNTHETIC:DISCOVERY",
                security="SYN:000004",
                name="Synthetic Discovery Issuer",
                side="UNASSIGNED",
            ),
        ],
        "exposures": [
            {
                "exposure_id": "EXPOSURE:SYNTHETIC:PACK",
                "issuer_id": "ISSUER:SYNTHETIC:PACK",
                "role": "PACK",
                "reference": "docs/local/pack-seed.json",
            },
            {
                "exposure_id": "EXPOSURE:SYNTHETIC:TEACHER",
                "issuer_id": "ISSUER:SYNTHETIC:TEACHER",
                "role": "TEACHER",
                "reference": "docs/local/teacher-case.md",
            },
        ],
    }


def test_accepts_a_local_preselection_ledger_with_disjoint_test_identity() -> None:
    result = validate_cohort_exposure_ledger(_ledger())

    assert result["state"] == "REVIEWABLE"
    assert result["issuer_count"] == 4
    assert result["intended_side_counts"] == {
        "EXCLUDED": 1,
        "PACK_BUILDING": 1,
        "TEST_ACQUISITION": 1,
        "UNASSIGNED": 1,
    }


def test_rejects_prior_teacher_or_campaign_exposure_on_test_side() -> None:
    ledger = _ledger()
    ledger["exposures"].append({
        "exposure_id": "EXPOSURE:SYNTHETIC:TEST:CAMPAIGN",
        "issuer_id": "ISSUER:SYNTHETIC:TEST",
        "role": "CAMPAIGN",
        "reference": "docs/local/prior-campaign.md",
    })

    result = validate_cohort_exposure_ledger(ledger)

    assert result["state"] == "INVALID"
    assert "test_acquisition_prior_exposure:ISSUER:SYNTHETIC:TEST:CAMPAIGN" in result["findings"]


def test_every_prior_exposure_role_blocks_a_test_side_issuer() -> None:
    for role in ("PACK", "TEACHER", "HOLDOUT", "TARGET", "CAMPAIGN"):
        ledger = _ledger()
        ledger["exposures"].append({
            "exposure_id": "EXPOSURE:SYNTHETIC:TEST:" + role,
            "issuer_id": "ISSUER:SYNTHETIC:TEST",
            "role": role,
            "reference": "docs/local/prior-" + role.lower() + ".md",
        })
        result = validate_cohort_exposure_ledger(ledger)
        assert result["state"] == "INVALID"
        assert (
            "test_acquisition_prior_exposure:ISSUER:SYNTHETIC:TEST:" + role
            in result["findings"]
        )


def test_rejects_mapping_shaped_exposures_instead_of_treating_them_as_empty() -> None:
    ledger = _ledger()
    ledger["exposures"] = {
        "exposure_id": "EXPOSURE:SYNTHETIC:TEST:CAMPAIGN",
        "issuer_id": "ISSUER:SYNTHETIC:TEST",
        "role": "CAMPAIGN",
        "reference": "docs/local/prior-campaign.md",
    }

    result = validate_cohort_exposure_ledger(ledger)

    assert result["state"] == "INVALID"
    assert result["findings"] == ["exposures.must_be_array"]


def test_rejects_same_legal_entity_recorded_under_two_issuer_ids() -> None:
    ledger = _ledger()
    ledger["issuer_identities"].append(_issuer(
        "ISSUER:SYNTHETIC:TEST:RENAMED",
        entity="ENTITY:SYNTHETIC:TEST",
        security="SYN:000099",
        name="Synthetic Test Issuer Renamed",
        side="UNASSIGNED",
    ))

    result = validate_cohort_exposure_ledger(ledger)

    assert result["state"] == "INVALID"
    assert (
        "issuer_identities[4].legal_entity_identity_collision:ENTITY:SYNTHETIC:TEST"
        in result["findings"]
    )


def test_rejects_security_or_name_alias_identity_collisions() -> None:
    ledger = _ledger()
    duplicate = deepcopy(ledger["issuer_identities"][3])
    duplicate.update({
        "issuer_id": "ISSUER:SYNTHETIC:COLLISION",
        "legal_entity_id": "ENTITY:SYNTHETIC:COLLISION",
        "security_identifiers": ["SYN:000003"],
        "issuer_name": "Another Synthetic Issuer",
        "aliases": ["Synthetic Test Issuer"],
    })
    ledger["issuer_identities"].append(duplicate)

    result = validate_cohort_exposure_ledger(ledger)

    assert result["state"] == "INVALID"
    assert (
        "issuer_identities[4].security_identifier_identity_collision:SYN:000003"
        in result["findings"]
    )
    assert any("issuer_name_identity_collision:synthetictestissuer" in finding for finding in result["findings"])


def test_rejects_case_and_separator_variants_of_the_same_security_identity() -> None:
    ledger = _ledger()
    duplicate = deepcopy(ledger["issuer_identities"][3])
    duplicate.update({
        "issuer_id": "ISSUER:SYNTHETIC:COLLISION",
        "legal_entity_id": "ENTITY:SYNTHETIC:COLLISION",
        "security_identifiers": ["syn : 000003"],
        "issuer_name": "Another Synthetic Issuer",
    })
    ledger["issuer_identities"].append(duplicate)

    result = validate_cohort_exposure_ledger(ledger)

    assert result["state"] == "INVALID"
    assert (
        "issuer_identities[4].security_identifier_identity_collision:SYN:000003"
        in result["findings"]
    )


def test_rejects_unknown_exposure_and_nonlocal_reference_before_selection() -> None:
    ledger = _ledger()
    ledger["exposures"].append({
        "exposure_id": "EXPOSURE:SYNTHETIC:UNKNOWN",
        "issuer_id": "ISSUER:SYNTHETIC:MISSING",
        "role": "HOLDOUT",
        "reference": "https://example.com/not-local",
    })

    result = validate_cohort_exposure_ledger(ledger)

    assert result["state"] == "INVALID"
    assert "exposures[2].issuer_not_in_identity_ledger:ISSUER:SYNTHETIC:MISSING" in result["findings"]
    assert "exposures[2].reference_must_be_local" in result["findings"]
