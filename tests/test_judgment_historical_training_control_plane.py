from __future__ import annotations

from copy import deepcopy
import sqlite3

import pytest

from scripts import judgment_historical_training as history
from scripts import judgment_historical_training_control_plane as control
from scripts import judgment_v5_control_plane as v5_control
from tests.test_judgment_v5_control_plane import _synthetic_preselection_receipt_envelopes


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    control.initialize(conn)
    h1, h2 = _synthetic_preselection_receipt_envelopes()
    v5_control.register_h1_static_cohort_receipt(conn, h1)
    v5_control.register_h2_action_screen_receipt(conn, h2)
    return conn


def _create_registry(conn: sqlite3.Connection) -> dict:
    return control.create_registry_from_registered_h1(
        conn,
        {"receipt_id": "SYNV5:H1:BASE", "receipt_version": 1},
        recorded_at="2021-01-02T00:00:00+00:00",
    )


def _predicate(registry: dict, *, h2_id: str = "SYNV5:H2:NETWORK") -> dict:
    return {
        "predicate_id": "PREDICATE:SYNV5:NETWORK:V1",
        "frozen_at": "2021-01-02T01:00:00+00:00",
        "action_screen_receipt_ref": {"receipt_id": h2_id, "receipt_version": 1},
        "mechanism_topology": registry["mechanism_topology"],
        "competitive_arena_id": registry["competitive_arena_id"],
        "source_cutoff_at": "2020-12-31T23:59:59+00:00",
        "selection_rule": "ALL_MATCHING_PREDECLARED_ROSTER",
        "requires_independent_control": True,
        "excludes_break_dispositions": ["KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"],
        "outcome_access_prohibited": True,
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
    }


def _batch(registry: dict) -> dict:
    predicate = registry["peer_recruitment_predicate"]
    reference = {"receipt_id": "HREG:BATCH:SYNV5:V1", "receipt_version": 1}
    return {
        "schema_version": history.CARRIER_REGISTRY_SCHEMA_VERSION,
        "batch_id": "BATCH:SYNV5:PEER:V1",
        "source_packet_ref": reference,
        "eligibility_predicate_id": predicate["predicate_id"],
        "received_at": "2021-01-03T00:00:00+00:00",
        "curator_id": "SYNV5:CURATOR",
        "static_sources": [{
            "source_id": "SYNV5:STATIC:PEER:ANNUAL",
            "url": "https://static.cninfo.com.cn/finalpage/2020-03-30/100000.PDF",
            "published_at": "2020-03-30T00:00:00+00:00",
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "issuer_id": "SYNV5:ISSUER:PEER:EXTRA",
            "responsibility_unit_id": "SYNV5:UNIT:PEER:EXTRA",
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
            "period_end": "2019-12-31",
            "field_refs": ["Synthetic static annual report PDF p12."],
        }],
        "carrier_static_coverage": [{
            "carrier_id": "SYNV5:CARRIER:PEER:EXTRA",
            "period_end": "2019-12-31",
            "field_id": "owner_cash_input",
            "source_id": "SYNV5:STATIC:PEER:ANNUAL",
            "field_ref": "Synthetic static annual report PDF p12.",
        }],
        "eligibility_population": [{
            "company_id": "SYNV5:COMPANY:PEER:EXTRA",
            "issuer_id": "SYNV5:ISSUER:PEER:EXTRA",
            "control_group_id": "SYNV5:CONTROL:PEER:EXTRA",
            "responsibility_unit_id": "SYNV5:UNIT:PEER:EXTRA",
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
            "eligibility_decision": "ELIGIBLE",
            "exclusion_reason": None,
        }],
        "carriers": [{
            "carrier_id": "SYNV5:CARRIER:PEER:EXTRA",
            "batch_id": "BATCH:SYNV5:PEER:V1",
            "company_id": "SYNV5:COMPANY:PEER:EXTRA",
            "issuer_id": "SYNV5:ISSUER:PEER:EXTRA",
            "control_group_id": "SYNV5:CONTROL:PEER:EXTRA",
            "responsibility_unit_id": "SYNV5:UNIT:PEER:EXTRA",
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
            "disposition": "ELIGIBLE_FOR_COMPARATIVE",
            "source_packet_ref": reference,
            "static_source_ids": ["SYNV5:STATIC:PEER:ANNUAL"],
            "eligibility_predicate_id": predicate["predicate_id"],
            "seed_disposition": None,
        }],
    }


def _resolve_pending(registry: dict) -> list[dict]:
    predicate_id = registry["peer_recruitment_predicate"]["predicate_id"]
    return [{
        "carrier_id": carrier["carrier_id"],
        "disposition": "ELIGIBLE_FOR_COMPARATIVE",
        "eligibility_predicate_id": predicate_id,
    } for carrier in registry["carriers"] if carrier["disposition"] == "PENDING_ACTION_WINDOW_REVIEW"]


def test_registered_registry_replays_h1_seed_and_resists_caller_mutation() -> None:
    conn = _conn()
    created = _create_registry(conn)
    registry_id = created["carrier_registry"]["registry_id"]
    caller_copy = deepcopy(created["carrier_registry"])
    caller_copy["state"] = "FROZEN"
    caller_copy["carriers"][0]["disposition"] = "ELIGIBLE_FOR_COMPARATIVE"

    invalid = history.validate_evidence_carrier_registry(caller_copy)
    assert not invalid["valid"]
    assert "registry.frozen_state_requires_peer_recruitment_predicate" in invalid["findings"]
    assert "registry.frozen_state_cannot_retain_pending_carriers" in invalid["findings"]
    canonical = control.load_registered_registry(conn, registry_id)
    assert canonical["state"] == "OPEN"
    assert canonical["carrier_registry"] == created["carrier_registry"]
    conn.close()


def test_predicate_must_reference_registered_parented_h2_and_its_real_cutoff() -> None:
    conn = _conn()
    created = _create_registry(conn)
    registry = created["carrier_registry"]
    with pytest.raises(control.HistoricalTrainingControlError) as exc_info:
        control.freeze_registered_peer_recruitment_predicate(
            conn, registry["registry_id"], _predicate(registry, h2_id="SYNV5:H2:UNKNOWN"),
            recorded_at="2021-01-02T01:00:00+00:00",
        )
    assert exc_info.value.code == "preselection_receipt_not_found"

    wrong_cutoff = _predicate(registry)
    wrong_cutoff["source_cutoff_at"] = "2021-01-01T00:00:00+00:00"
    with pytest.raises(control.HistoricalTrainingControlError) as exc_info:
        control.freeze_registered_peer_recruitment_predicate(
            conn, registry["registry_id"], wrong_cutoff, recorded_at="2021-01-02T01:00:00+00:00",
        )
    assert exc_info.value.code == "peer_recruitment_source_cutoff_mismatch"

    premature = _predicate(registry)
    with pytest.raises(control.HistoricalTrainingControlError) as exc_info:
        control.freeze_registered_peer_recruitment_predicate(
            conn, registry["registry_id"], premature, recorded_at="2021-01-02T00:30:00+00:00",
        )
    assert exc_info.value.code == "peer_recruitment_predicate_time_mismatch"
    conn.close()


def test_registry_chronology_compares_instants_not_offset_strings() -> None:
    conn = _conn()
    created = control.create_registry_from_registered_h1(
        conn,
        {"receipt_id": "SYNV5:H1:BASE", "receipt_version": 1},
        recorded_at="2021-01-01T02:00:00+00:00",
    )
    predicate = _predicate(created["carrier_registry"])
    # This lexically follows 01:00+00:00, but it is 00:00 UTC: before the
    # immutable H2 receipt and before the registry itself.
    predicate["frozen_at"] = "2021-01-01T10:00:00+10:00"
    with pytest.raises(control.HistoricalTrainingControlError) as exc_info:
        control.freeze_registered_peer_recruitment_predicate(
            conn, created["carrier_registry"]["registry_id"], predicate,
            recorded_at="2021-01-01T10:00:00+10:00",
        )
    assert exc_info.value.code == "peer_recruitment_predicate_precedes_h2_receipt"

    # A later UTC instant is valid even when its local clock display is lower.
    predicate["frozen_at"] = "2021-01-01T00:30:00-03:00"
    result = control.freeze_registered_peer_recruitment_predicate(
        conn, created["carrier_registry"]["registry_id"], predicate,
        recorded_at="2021-01-01T00:30:00-03:00",
    )
    assert result["carrier_registry"]["peer_recruitment_predicate"]["frozen_at"] == "2021-01-01T00:30:00-03:00"
    stored = control.load_registered_registry(conn, created["carrier_registry"]["registry_id"])
    assert conn.execute(
        f"SELECT recorded_at FROM {control.EVENT_TABLE} WHERE registry_id = ? ORDER BY sequence_number DESC",
        (stored["carrier_registry"]["registry_id"],),
    ).fetchone()[0] == "2021-01-01T03:30:00+00:00"
    conn.close()


def test_registered_static_batch_is_complete_cutoff_safe_and_immutable() -> None:
    conn = _conn()
    created = _create_registry(conn)
    registry_id = created["carrier_registry"]["registry_id"]
    frozen_predicate = control.freeze_registered_peer_recruitment_predicate(
        conn, registry_id, _predicate(created["carrier_registry"]), recorded_at="2021-01-02T01:00:00+00:00",
    )["carrier_registry"]

    post_cutoff = _batch(frozen_predicate)
    post_cutoff["static_sources"][0]["published_at"] = "2021-01-01T00:00:00+00:00"
    with pytest.raises(control.HistoricalTrainingControlError) as exc_info:
        control.register_static_peer_batch(conn, registry_id, post_cutoff, recorded_at="2021-01-03T00:00:00+00:00")
    assert exc_info.value.code == "peer_recruitment_batch_invalid"
    assert "published_at_must_be_strictly_before_predicate_cutoff" in exc_info.value.detail

    cherry_picked = _batch(frozen_predicate)
    cherry_picked["eligibility_population"].append({
        "company_id": "SYNV5:COMPANY:PEER:OMITTED",
        "issuer_id": "SYNV5:ISSUER:PEER:OMITTED",
        "control_group_id": "SYNV5:CONTROL:PEER:OMITTED",
        "responsibility_unit_id": "SYNV5:UNIT:PEER:OMITTED",
        "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
        "unit": "RMB",
        "eligibility_decision": "ELIGIBLE",
        "exclusion_reason": None,
    })
    with pytest.raises(control.HistoricalTrainingControlError) as exc_info:
        control.register_static_peer_batch(conn, registry_id, cherry_picked, recorded_at="2021-01-03T00:00:00+00:00")
    assert exc_info.value.code == "peer_recruitment_batch_invalid"
    assert "eligibility_population_must_exactly_match_frozen_predicate" in exc_info.value.detail

    batch = _batch(frozen_predicate)
    first = control.register_static_peer_batch(conn, registry_id, batch, recorded_at="2021-01-03T00:00:00+00:00")
    replay = control.register_static_peer_batch(conn, registry_id, deepcopy(batch), recorded_at="2021-01-03T00:00:00+00:00")
    assert first["idempotent"] is False
    assert replay["idempotent"] is True
    replacement = deepcopy(batch)
    replacement["static_sources"][0]["field_refs"] = ["Changed PDF p13."]
    with pytest.raises(control.HistoricalTrainingControlError) as exc_info:
        control.register_static_peer_batch(conn, registry_id, replacement, recorded_at="2021-01-03T00:00:00+00:00")
    assert exc_info.value.code == "peer_recruitment_batch_receipt_conflict"
    conn.close()


def test_registry_event_time_is_monotonic_after_predicate_freeze() -> None:
    conn = _conn()
    created = _create_registry(conn)
    registry_id = created["carrier_registry"]["registry_id"]
    frozen_predicate = control.freeze_registered_peer_recruitment_predicate(
        conn, registry_id, _predicate(created["carrier_registry"]), recorded_at="2021-01-02T01:00:00+00:00",
    )["carrier_registry"]
    with pytest.raises(control.HistoricalTrainingControlError) as exc_info:
        control.resolve_registered_pending_carriers(
            conn, registry_id, _resolve_pending(frozen_predicate), recorded_at="2021-01-02T00:30:00+00:00",
        )
    assert exc_info.value.code == "registry_event_time_regression"
    conn.close()


def test_only_recorded_transitions_can_close_registry_and_breaks_cannot_reenter() -> None:
    conn = _conn()
    created = _create_registry(conn)
    registry_id = created["carrier_registry"]["registry_id"]
    registry = control.freeze_registered_peer_recruitment_predicate(
        conn, registry_id, _predicate(created["carrier_registry"]), recorded_at="2021-01-02T01:00:00+00:00",
    )["carrier_registry"]
    registry = control.register_static_peer_batch(conn, registry_id, _batch(registry), recorded_at="2021-01-03T00:00:00+00:00")["carrier_registry"]
    resolved = control.resolve_registered_pending_carriers(
        conn, registry_id, _resolve_pending(registry), recorded_at="2021-01-03T01:00:00+00:00",
    )["carrier_registry"]
    closed = control.freeze_registered_carrier_registry(
        conn, registry_id, recorded_at="2021-01-03T02:00:00+00:00")
    assert closed["carrier_registry"]["state"] == "FROZEN"
    assert all(carrier["disposition"] == "ELIGIBLE_FOR_COMPARATIVE" for carrier in resolved["carriers"])
    later_batch = _batch(closed["carrier_registry"])
    later_batch["batch_id"] = "BATCH:SYNV5:PEER:LATE"
    later_batch["source_packet_ref"] = {"receipt_id": "HREG:BATCH:SYNV5:LATE", "receipt_version": 1}
    later_batch["static_sources"][0]["source_id"] = "SYNV5:STATIC:PEER:LATE"
    later_batch["carrier_static_coverage"][0]["source_id"] = "SYNV5:STATIC:PEER:LATE"
    later_batch["carriers"][0]["carrier_id"] = "SYNV5:CARRIER:PEER:LATE"
    later_batch["carriers"][0]["batch_id"] = later_batch["batch_id"]
    later_batch["carriers"][0]["company_id"] = "SYNV5:COMPANY:PEER:LATE"
    later_batch["carriers"][0]["issuer_id"] = "SYNV5:ISSUER:PEER:LATE"
    later_batch["carriers"][0]["control_group_id"] = "SYNV5:CONTROL:PEER:LATE"
    later_batch["carriers"][0]["responsibility_unit_id"] = "SYNV5:UNIT:PEER:LATE"
    later_batch["carriers"][0]["source_packet_ref"] = later_batch["source_packet_ref"]
    later_batch["carriers"][0]["static_source_ids"] = ["SYNV5:STATIC:PEER:LATE"]
    later_batch["eligibility_population"][0].update({
        "company_id": "SYNV5:COMPANY:PEER:LATE",
        "issuer_id": "SYNV5:ISSUER:PEER:LATE",
        "control_group_id": "SYNV5:CONTROL:PEER:LATE",
        "responsibility_unit_id": "SYNV5:UNIT:PEER:LATE",
    })
    later_batch["static_sources"][0].update({
        "issuer_id": "SYNV5:ISSUER:PEER:LATE",
        "responsibility_unit_id": "SYNV5:UNIT:PEER:LATE",
    })
    with pytest.raises(control.HistoricalTrainingControlError) as exc_info:
        control.register_static_peer_batch(conn, registry_id, later_batch, recorded_at="2021-01-03T03:00:00+00:00")
    assert exc_info.value.code == "peer_recruitment_batch_invalid"
    # A new H1 with material breaks projects those breaks as immutable seed
    # dispositions; no resolution API can name a non-pending carrier.
    conn.close()
