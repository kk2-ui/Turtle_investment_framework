from __future__ import annotations

from copy import deepcopy
import sqlite3

import pytest

from scripts import judgment_historical_training_control_plane as historical_control
from scripts import judgment_v5_control_plane as v5_control
from scripts import judgment_v5_registry_control_plane as registry_control
from tests.test_judgment_historical_training_control_plane import _predicate, _resolve_pending
from tests.test_judgment_v5_control_plane import (
    _canonical_bundle,
    _refresh_reviewed_selection_contract,
    _synthetic_preselection_receipt_envelopes,
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    registry_control.initialize(conn)
    h1, h2 = _synthetic_preselection_receipt_envelopes()
    v5_control.register_h1_static_cohort_receipt(conn, h1)
    v5_control.register_h2_action_screen_receipt(conn, h2)
    return conn


def _open_resolved_registry(conn: sqlite3.Connection) -> dict:
    created = historical_control.create_registry_from_registered_h1(
        conn,
        {"receipt_id": "SYNV5:H1:BASE", "receipt_version": 1},
        recorded_at="2021-01-02T00:00:00+00:00",
    )
    registry_id = created["carrier_registry"]["registry_id"]
    registry = historical_control.freeze_registered_peer_recruitment_predicate(
        conn, registry_id, _predicate(created["carrier_registry"]),
        recorded_at="2021-01-02T01:00:00+00:00",
    )["carrier_registry"]
    return historical_control.resolve_registered_pending_carriers(
        conn, registry_id, _resolve_pending(registry), recorded_at="2021-01-02T02:00:00+00:00",
    )["carrier_registry"]


def _peer_batch(registry: dict) -> dict:
    predicate = registry["peer_recruitment_predicate"]
    periods = ["2015-12-31", "2016-12-31", "2017-12-31", "2018-12-31", "2019-12-31"]
    sources = [{
        "source_id": f"SYNV5:STATIC:PEER:EXTRA:{period}",
        "url": f"https://static.cninfo.com.cn/finalpage/{period[:4]}-03-30/900000-{period}.PDF",
        "published_at": f"{int(period[:4]) + 1}-03-30T00:00:00+00:00",
        "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
        "issuer_id": "SYNV5:ISSUER:PEER:EXTRA",
        "responsibility_unit_id": "SYNV5:UNIT:PEER:EXTRA",
        "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
        "unit": "RMB",
        "period_end": period,
        "field_refs": ["Synthetic peer annual report PDF p12."],
    } for period in periods]
    reference = {"receipt_id": "HREG:BATCH:SYNV5:EXTRA:V1", "receipt_version": 1}
    return {
        "schema_version": "turtle-evidence-carrier-registry.v1",
        "batch_id": "BATCH:SYNV5:EXTRA:V1",
        "source_packet_ref": reference,
        "eligibility_predicate_id": predicate["predicate_id"],
        "received_at": "2021-01-02T01:30:00+00:00",
        "curator_id": "SYNV5:CURATOR",
        "static_sources": sources,
        "carrier_static_coverage": [
            *[
                {
                    "carrier_id": "SYNV5:CARRIER:PEER:EXTRA",
                    "period_end": source["period_end"],
                    "field_id": "unit_price",
                    "source_id": source["source_id"],
                    "field_ref": "Synthetic peer annual report PDF p12.",
                }
                for source in sources[:3]
            ],
            *[
                {
                    "carrier_id": "SYNV5:CARRIER:PEER:EXTRA",
                    "period_end": source["period_end"],
                    "field_id": "owner_cash_input",
                    "source_id": source["source_id"],
                    "field_ref": "Synthetic peer annual report PDF p12.",
                }
                for source in sources
            ],
        ],
        "eligibility_population": deepcopy(predicate["peer_recruitment_population"]),
        "carriers": [{
            "carrier_id": "SYNV5:CARRIER:PEER:EXTRA",
            "batch_id": "BATCH:SYNV5:EXTRA:V1",
            "company_id": "SYNV5:COMPANY:PEER:EXTRA",
            "issuer_id": "SYNV5:ISSUER:PEER:EXTRA",
            "control_group_id": "SYNV5:CONTROL:PEER:EXTRA",
            "responsibility_unit_id": "SYNV5:UNIT:PEER:EXTRA",
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
            "disposition": "ELIGIBLE_FOR_COMPARATIVE",
            "source_packet_ref": reference,
            "static_source_ids": [source["source_id"] for source in sources],
            "eligibility_predicate_id": predicate["predicate_id"],
            "seed_disposition": None,
        }],
    }


def _open_resolved_registry_with_peer_batch(conn: sqlite3.Connection) -> dict:
    created = historical_control.create_registry_from_registered_h1(
        conn,
        {"receipt_id": "SYNV5:H1:BASE", "receipt_version": 1},
        recorded_at="2021-01-02T00:00:00+00:00",
    )
    registry_id = created["carrier_registry"]["registry_id"]
    registry = historical_control.freeze_registered_peer_recruitment_predicate(
        conn, registry_id, _predicate(created["carrier_registry"]),
        recorded_at="2021-01-02T01:00:00+00:00",
    )["carrier_registry"]
    registry = historical_control.register_static_peer_batch(
        conn, registry_id, _peer_batch(registry), recorded_at="2021-01-02T01:30:00+00:00",
    )["carrier_registry"]
    return historical_control.resolve_registered_pending_carriers(
        conn, registry_id, _resolve_pending(registry), recorded_at="2021-01-02T02:00:00+00:00",
    )["carrier_registry"]


def _bundle() -> dict:
    bundle = _canonical_bundle()
    bundle["selection_freeze_id"] = "SYNV5:FREEZE:REGISTRY-EPOCH"
    bundle["candidate_id"] = "SYNV5:CANDIDATE:REGISTRY-EPOCH"
    bundle["episode_collision_key"] = "SYNV5:COLLISION:REGISTRY-EPOCH"
    bundle["sealed_at"] = "2021-01-03T00:00:00+00:00"
    bundle["recorded_at"] = "2021-01-03T00:00:00+00:00"
    _refresh_reviewed_selection_contract(bundle)
    return bundle


def _binding(conn: sqlite3.Connection, bundle: dict, registry: dict, *, peer_issuers: list[str] | None = None) -> dict:
    event_sequence = conn.execute(
        f"SELECT MAX(sequence_number) FROM {historical_control.EVENT_TABLE} WHERE registry_id = ?",
        (registry["registry_id"],),
    ).fetchone()[0]
    by_issuer = {carrier["issuer_id"]: carrier for carrier in registry["carriers"]}
    target = by_issuer["ISSUER:TARGET"]
    peers = [by_issuer[issuer] for issuer in (peer_issuers or [f"ISSUER:PEER{index}" for index in range(1, 4)])]
    excluded = [carrier for carrier in registry["carriers"] if carrier["carrier_id"] not in {
        target["carrier_id"], *(peer["carrier_id"] for peer in peers),
    }]
    ledger_rows = []
    for carrier, disposition, reason in [
        (target, "TARGET", "IMPLEMENTED_ACTION_FOCAL_CARRIER"),
        *[(peer, "EXTERNAL_SHOCK_COMPARATOR", "PREDECLARED_ELIGIBLE_EXTERNAL_COMPARATOR") for peer in peers],
        *[(carrier, "EXCLUDED_PREOUTCOME", "NOT_IN_FINAL_FROZEN_COMPARATOR_TOPOLOGY") for carrier in excluded],
    ]:
        ledger_rows.append({
            "carrier_id": carrier["carrier_id"],
            "panel_disposition": disposition,
            "reason_code": reason,
            "source_ids": [carrier["static_source_ids"][0]],
        })
    binding = {
        "schema_version": "judgment-selection-v5-registry-binding.v1",
        "admission_epoch_id": "JUDGMENT_SELECTION_ADMISSION_V5_REGISTRY_V1",
        "binding_id": "SYNV5:REGISTRY-BINDING:CONTROL:V1",
        "selection_freeze_id": bundle["selection_freeze_id"],
        "registry_id": registry["registry_id"],
        "preseal_registry_event_sequence": event_sequence,
        "target_carrier_id": target["carrier_id"],
        "ordered_panel_carrier_ids": [peer["carrier_id"] for peer in peers],
        "registry_selection_arena_bridge": {
            "registry_competitive_arena_id": registry["competitive_arena_id"],
            "selection_competitive_arena_id": bundle["competitive_arena"]["competitive_arena_id"],
            "relation": "MECHANISM_COMPATIBLE",
            "source_ids": [target["static_source_ids"][0]],
        },
        "registry_panel_disposition_ledger": ledger_rows,
        "registry_preoutcome_review": {
            "review_id": "SYNV5:REGISTRY-REVIEW:CONTROL:V1",
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


def _registry_manifest_source(source: dict) -> dict:
    return {
        "source_id": source["source_id"],
        "source_lane": "STAGE0_STATIC",
        "publisher": v5_control.STATIC_CNINFO_PUBLISHER,
        "official_artifact_id": source["source_id"],
        "source_url": source["url"],
        "source_type": source["source_type"],
        "issuer_id": source["issuer_id"],
        "responsibility_unit_id": source["responsibility_unit_id"],
        "perimeter_id": source["perimeter_id"],
        "unit": source["unit"],
        "published_at_or_date": source["published_at"],
        "availability_precision": "INTRADAY",
        "outcome_visibility": "PREOUTCOME_VISIBLE",
    }


def _bundle_with_recruited_peer() -> dict:
    bundle = _bundle()
    batch = _peer_batch({"peer_recruitment_predicate": {
        "predicate_id": "ignored",
        "peer_recruitment_population": [{
            "company_id": "SYNV5:COMPANY:PEER:EXTRA",
            "issuer_id": "SYNV5:ISSUER:PEER:EXTRA",
            "control_group_id": "SYNV5:CONTROL:PEER:EXTRA",
            "responsibility_unit_id": "SYNV5:UNIT:PEER:EXTRA",
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
            "eligibility_decision": "ELIGIBLE",
            "exclusion_reason": None,
        }],
    }})
    sources = batch["static_sources"]
    recruited_member = {
        "company_id": "SYNV5:COMPANY:PEER:EXTRA",
        "issuer_id": "SYNV5:ISSUER:PEER:EXTRA",
        "responsibility_unit_id": "SYNV5:UNIT:PEER:EXTRA",
        "control_group_id": "SYNV5:CONTROL:PEER:EXTRA",
        "boundary": {
            "responsibility_unit_id": "SYNV5:UNIT:PEER:EXTRA",
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
        },
        "carrier_identity_source_ids": [sources[0]["source_id"]],
        "d2_or_cost_field_history": [
            {"period_end": source["period_end"], "field_id": "unit_price", "source_id": source["source_id"]}
            for source in sources[:3]
        ],
        "d3_d4_field_history": [
            {"period_end": source["period_end"], "field_id": "owner_cash_input", "source_id": source["source_id"]}
            for source in sources
        ],
    }
    bundle["cohort_snapshot"]["members"] = [
        recruited_member if member["issuer_id"] == "ISSUER:PEER3" else member
        for member in bundle["cohort_snapshot"]["members"]
    ]
    for member in bundle["counterfactual_panel"]["members"]:
        if member["issuer_id"] == "ISSUER:PEER3":
            member["issuer_id"] = recruited_member["issuer_id"]
            member["control_group_id"] = recruited_member["control_group_id"]
    for row in bundle["outcome_contract"]["frozen_raw_matrix"]:
        if row["issuer_id"] == "ISSUER:PEER3":
            row["issuer_id"] = recruited_member["issuer_id"]
    bundle["source_manifest"].extend(_registry_manifest_source(source) for source in sources)
    _refresh_reviewed_selection_contract(bundle)
    return bundle


def test_registry_epoch_atomically_closes_persisted_registry_and_reuses_v5_lifecycle() -> None:
    conn = _conn()
    registry = _open_resolved_registry(conn)
    bundle = _bundle()
    binding = _binding(conn, bundle, registry)

    sealed = registry_control.seal_registry_aware_v5_freeze(conn, bundle, binding)

    assert sealed == {
        "sealed": True,
        "selection_freeze_id": bundle["selection_freeze_id"],
        "idempotent": False,
    }
    assert historical_control.load_registered_registry(conn, registry["registry_id"])["state"] == "FROZEN"
    loaded = registry_control.load_registry_epoch_binding(conn, bundle["selection_freeze_id"])
    assert loaded["binding"] == binding
    assert registry_control.seal_registry_aware_v5_freeze(conn, bundle, deepcopy(binding))["idempotent"] is True

    authorized = v5_control.authorize_outcome_access(conn, {
        "selection_freeze_id": bundle["selection_freeze_id"],
        "authorization_id": "SYNV5:AUTH:REGISTRY-EPOCH",
        "custodian_id": "SYNV5:CUSTODIAN",
        "actor_id": "SYNV5:PREOUTCOME_REVIEWER",
        "effective_at": "2022-01-15T00:00:00+00:00",
    })
    assert authorized["event"]["event_type"] == "OUTCOME_ACCESS_AUTHORIZED"
    conn.close()


def test_registry_epoch_admits_one_immutable_recruited_peer_without_changing_legacy_v5() -> None:
    conn = _conn()
    registry = _open_resolved_registry_with_peer_batch(conn)
    bundle = _bundle_with_recruited_peer()
    binding = _binding(
        conn, bundle, registry,
        peer_issuers=["ISSUER:PEER1", "ISSUER:PEER2", "SYNV5:ISSUER:PEER:EXTRA"],
    )

    sealed = registry_control.seal_registry_aware_v5_freeze(conn, bundle, binding)

    assert sealed["sealed"] is True
    assert historical_control.load_registered_registry(conn, registry["registry_id"])["state"] == "FROZEN"
    with pytest.raises(v5_control.ControlPlaneError) as exc_info:
        v5_control.seal_freeze(conn, bundle)
    assert exc_info.value.code == "h1_cohort_member_not_declared"
    conn.close()


def test_registry_epoch_rejects_recruited_peer_period_drift_before_any_freeze_write() -> None:
    conn = _conn()
    registry = _open_resolved_registry_with_peer_batch(conn)
    bundle = _bundle_with_recruited_peer()
    recruited = next(member for member in bundle["cohort_snapshot"]["members"] if member["issuer_id"] == "SYNV5:ISSUER:PEER:EXTRA")
    recruited["d3_d4_field_history"][0]["period_end"] = "2014-12-31"
    _refresh_reviewed_selection_contract(bundle)
    binding = _binding(
        conn, bundle, registry,
        peer_issuers=["ISSUER:PEER1", "ISSUER:PEER2", "SYNV5:ISSUER:PEER:EXTRA"],
    )

    with pytest.raises(registry_control.RegistryEpochControlError) as exc_info:
        registry_control.seal_registry_aware_v5_freeze(conn, bundle, binding)

    assert exc_info.value.code == "registry_epoch_recruited_field_period_or_issuer_mismatch"
    assert conn.execute(f"SELECT COUNT(*) FROM {v5_control.FREEZE_TABLE}").fetchone()[0] == 0
    conn.close()


@pytest.mark.parametrize(
    ("history_name", "mutation"),
    [
        ("d2_or_cost_field_history", ("field_id", "unsupported_unit_price")),
        ("d3_d4_field_history", ("field_id", "unsupported_owner_cash")),
    ],
)
def test_registry_epoch_rejects_recruited_field_not_covered_by_immutable_batch(
    history_name: str, mutation: tuple[str, str],
) -> None:
    conn = _conn()
    registry = _open_resolved_registry_with_peer_batch(conn)
    bundle = _bundle_with_recruited_peer()
    recruited = next(member for member in bundle["cohort_snapshot"]["members"] if member["issuer_id"] == "SYNV5:ISSUER:PEER:EXTRA")
    field, value = mutation
    recruited[history_name][0][field] = value
    _refresh_reviewed_selection_contract(bundle)
    binding = _binding(
        conn, bundle, registry,
        peer_issuers=["ISSUER:PEER1", "ISSUER:PEER2", "SYNV5:ISSUER:PEER:EXTRA"],
    )

    with pytest.raises(registry_control.RegistryEpochControlError) as exc_info:
        registry_control.seal_registry_aware_v5_freeze(conn, bundle, binding)

    assert exc_info.value.code == "registry_epoch_recruited_field_coverage_mismatch"
    assert conn.execute(f"SELECT COUNT(*) FROM {v5_control.FREEZE_TABLE}").fetchone()[0] == 0
    conn.close()


def test_registry_epoch_conflict_rolls_back_freeze_and_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _conn()
    registry = _open_resolved_registry(conn)
    bundle = _bundle()
    binding = _binding(conn, bundle, registry)
    original = registry_control._require_registry_panel_projection

    def interleave(*args, **kwargs) -> None:
        original(*args, **kwargs)
        fresh = historical_control._registry_row(conn, registry["registry_id"])
        historical_control._save_registry(
            conn,
            fresh,
            historical_control._loads(fresh["registry_json"]),
            event_kind="TEST_INTERLEAVING_UPDATE",
            payload={},
            recorded_at="2021-01-02T02:30:00+00:00",
        )

    monkeypatch.setattr(registry_control, "_require_registry_panel_projection", interleave)
    with pytest.raises(registry_control.RegistryEpochControlError) as exc_info:
        registry_control.seal_registry_aware_v5_freeze(conn, bundle, binding)

    assert exc_info.value.code == "carrier_registry_state_conflict"
    assert conn.execute(f"SELECT COUNT(*) FROM {v5_control.FREEZE_TABLE}").fetchone()[0] == 0
    assert conn.execute(f"SELECT COUNT(*) FROM {registry_control.BINDING_TABLE}").fetchone()[0] == 0
    conn.close()


def test_registry_epoch_binding_id_conflict_is_stable_and_does_not_write() -> None:
    conn = _conn()
    registry = _open_resolved_registry(conn)
    first_bundle = _bundle()
    first_binding = _binding(conn, first_bundle, registry)
    registry_control.seal_registry_aware_v5_freeze(conn, first_bundle, first_binding)

    second_bundle = _bundle()
    second_bundle["selection_freeze_id"] = "SYNV5:FREEZE:REGISTRY-EPOCH:SECOND"
    second_bundle["candidate_id"] = "SYNV5:CANDIDATE:REGISTRY-EPOCH:SECOND"
    second_bundle["episode_collision_key"] = "SYNV5:COLLISION:REGISTRY-EPOCH:SECOND"
    _refresh_reviewed_selection_contract(second_bundle)
    second_binding = _binding(conn, second_bundle, registry)
    with pytest.raises(registry_control.RegistryEpochControlError) as exc_info:
        registry_control.seal_registry_aware_v5_freeze(conn, second_bundle, second_binding)

    assert exc_info.value.code == "registry_epoch_binding_id_conflict"
    assert conn.execute(f"SELECT COUNT(*) FROM {v5_control.FREEZE_TABLE}").fetchone()[0] == 1
    assert conn.execute(f"SELECT COUNT(*) FROM {registry_control.BINDING_TABLE}").fetchone()[0] == 1
    conn.close()


def test_registry_epoch_refuses_pending_or_mutated_persisted_provenance_before_freeze_write() -> None:
    conn = _conn()
    created = historical_control.create_registry_from_registered_h1(
        conn,
        {"receipt_id": "SYNV5:H1:BASE", "receipt_version": 1},
        recorded_at="2021-01-02T00:00:00+00:00",
    )
    registry_id = created["carrier_registry"]["registry_id"]
    registry = historical_control.freeze_registered_peer_recruitment_predicate(
        conn, registry_id, _predicate(created["carrier_registry"]),
        recorded_at="2021-01-02T01:00:00+00:00",
    )["carrier_registry"]
    bundle = _bundle()
    binding = _binding(conn, bundle, registry)
    with pytest.raises(registry_control.RegistryEpochControlError) as exc_info:
        registry_control.seal_registry_aware_v5_freeze(conn, bundle, binding)
    assert exc_info.value.code == "registry_epoch_pending_carrier"
    assert conn.execute(f"SELECT COUNT(*) FROM {v5_control.FREEZE_TABLE}").fetchone()[0] == 0

    registry = historical_control.resolve_registered_pending_carriers(
        conn, registry_id, _resolve_pending(registry), recorded_at="2021-01-02T02:00:00+00:00",
    )["carrier_registry"]
    binding = _binding(conn, bundle, registry)
    mutated = deepcopy(bundle)
    mutated["source_manifest"][0]["issuer_id"] = "ISSUER:MUTATED"
    _refresh_reviewed_selection_contract(mutated)
    with pytest.raises(registry_control.RegistryEpochControlError) as exc_info:
        registry_control.seal_registry_aware_v5_freeze(conn, mutated, binding)
    assert exc_info.value.code == "source_manifest_identity_mismatch"
    assert conn.execute(f"SELECT COUNT(*) FROM {v5_control.FREEZE_TABLE}").fetchone()[0] == 0
    conn.close()
