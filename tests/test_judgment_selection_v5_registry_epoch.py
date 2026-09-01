from __future__ import annotations

from copy import deepcopy

from scripts import judgment_selection_v5_registry_epoch as registry_epoch
from tests.test_judgment_v5_control_plane import _canonical_bundle


def _binding(bundle: dict) -> dict:
    source_id = bundle["source_manifest"][0]["source_id"]
    binding = {
        "schema_version": registry_epoch.SCHEMA_VERSION,
        "admission_epoch_id": registry_epoch.ADMISSION_EPOCH_ID,
        "binding_id": "SYNV5:REGISTRY-BINDING:V1",
        "selection_freeze_id": bundle["selection_freeze_id"],
        "registry_id": "SYNV5:CARRIER-REGISTRY:V1",
        "preseal_registry_event_sequence": 4,
        "target_carrier_id": "SYNV5:CARRIER:TARGET",
        "ordered_panel_carrier_ids": [
            "SYNV5:CARRIER:PEER1",
            "SYNV5:CARRIER:PEER2",
            "SYNV5:CARRIER:PEER3",
        ],
        "registry_selection_arena_bridge": {
            "registry_competitive_arena_id": "ARENA:SYNTHETIC:NATIONAL",
            "selection_competitive_arena_id": bundle["competitive_arena"]["competitive_arena_id"],
            "relation": "MECHANISM_COMPATIBLE",
            "source_ids": [source_id],
        },
        "registry_panel_disposition_ledger": [
            {
                "carrier_id": "SYNV5:CARRIER:TARGET",
                "panel_disposition": "TARGET",
                "reason_code": "IMPLEMENTED_ACTION_FOCAL_CARRIER",
                "source_ids": [source_id],
            },
            *[
                {
                    "carrier_id": f"SYNV5:CARRIER:PEER{index}",
                    "panel_disposition": "EXTERNAL_SHOCK_COMPARATOR",
                    "reason_code": "PREDECLARED_ELIGIBLE_EXTERNAL_COMPARATOR",
                    "source_ids": [source_id],
                }
                for index in range(1, 4)
            ],
        ],
        "registry_preoutcome_review": {
            "review_id": "SYNV5:REGISTRY-REVIEW:V1",
            "pre_outcome_designer_id": bundle["independent_pre_outcome_review"]["pre_outcome_designer_id"],
            "reviewer_id": bundle["independent_pre_outcome_review"]["reviewer_id"],
            "reviewed_at": bundle["independent_pre_outcome_review"]["reviewed_at"],
            "verdict": "ACCEPTED",
            "reviewer_outcome_body_access": "NONE",
            "reviewer_outcome_metadata_access": "NONE",
            "reviewed_binding": {},
        },
    }
    binding["registry_preoutcome_review"]["reviewed_binding"] = {
        field: deepcopy(binding[field])
        for field in (
            "schema_version", "admission_epoch_id", "binding_id", "selection_freeze_id", "registry_id",
            "preseal_registry_event_sequence", "target_carrier_id", "ordered_panel_carrier_ids", "registry_selection_arena_bridge",
            "registry_panel_disposition_ledger",
        )
    }
    return binding


def test_registry_binding_is_a_reviewed_preseal_receipt_not_a_second_root() -> None:
    bundle = _canonical_bundle()
    binding = _binding(bundle)

    result = registry_epoch.validate_registry_aware_v5_binding(bundle, binding)

    assert result == {
        "valid": True,
        "admission_status": "SELECTION_ADMITTED",
        "findings": [],
    }


def test_registry_binding_rejects_panel_and_review_mutation() -> None:
    bundle = _canonical_bundle()
    binding = _binding(bundle)
    binding["ordered_panel_carrier_ids"] = binding["ordered_panel_carrier_ids"][:1]
    invalid_capacity = registry_epoch.validate_registry_aware_v5_binding(bundle, binding)
    assert invalid_capacity["valid"] is False
    assert "binding_external_comparator_capacity_or_identity_invalid" in invalid_capacity["findings"]
    assert "binding_review_binding_does_not_match" in invalid_capacity["findings"]

    binding = _binding(bundle)
    binding["registry_preoutcome_review"]["reviewed_binding"]["registry_id"] = "MUTATED"
    invalid_review = registry_epoch.validate_registry_aware_v5_binding(bundle, binding)
    assert invalid_review["valid"] is False
    assert invalid_review["findings"] == ["binding_review_binding_does_not_match"]
