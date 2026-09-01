#!/usr/bin/env python3
"""Registry-aware pre-seal admission for a later, separate V5 epoch.

This module never changes legacy ``seal_freeze``: that API continues to bind
its closed H1 roster exactly.  The new entrypoint pairs the same V5 economic
bundle with a narrow provenance binding, resolves both from persisted receipts
and then stores the original V5 root in the existing freeze/event lifecycle.
"""

from __future__ import annotations

from copy import deepcopy
import sqlite3
from typing import Any

try:
    from scripts import judgment_historical_training as history
    from scripts import judgment_historical_training_control_plane as historical_control
    from scripts import judgment_selection_v5_registry_epoch as epoch
    from scripts import judgment_v5_control_plane as v5_control
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import judgment_historical_training as history
    import judgment_historical_training_control_plane as historical_control
    import judgment_selection_v5_registry_epoch as epoch
    import judgment_v5_control_plane as v5_control


SCHEMA_VERSION = "judgment-v5-registry-control-plane.v1"
BINDING_TABLE = "judgment_v5_registry_epoch_bindings"


class RegistryEpochControlError(v5_control.ControlPlaneError):
    """A stable error raised before a registry-epoch freeze is written."""


def initialize(conn: sqlite3.Connection) -> None:
    """Create the binding namespace beside existing historical/V5 controls."""
    historical_control.initialize(conn)
    with conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {BINDING_TABLE} (
                selection_freeze_id TEXT PRIMARY KEY,
                binding_id TEXT NOT NULL UNIQUE,
                registry_id TEXT NOT NULL,
                preseal_registry_event_sequence INTEGER NOT NULL,
                binding_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (selection_freeze_id)
                    REFERENCES {v5_control.FREEZE_TABLE}(selection_freeze_id),
                FOREIGN KEY (registry_id)
                    REFERENCES {historical_control.REGISTRY_TABLE}(registry_id)
            )"""
        )


def _required_text(value: dict[str, Any], field: str) -> str:
    try:
        return v5_control._required_text(value, field)
    except v5_control.ControlPlaneError as exc:
        raise RegistryEpochControlError(exc.code, exc.detail) from exc


def _positive_integer(value: Any, *, field: str) -> int:
    try:
        return v5_control._positive_integer(value, field=field)
    except v5_control.ControlPlaneError as exc:
        raise RegistryEpochControlError(exc.code, exc.detail) from exc


def _parse_time(value: Any, *, field: str):
    try:
        return v5_control._parse_time(value, field=field)
    except v5_control.ControlPlaneError as exc:
        raise RegistryEpochControlError(exc.code, exc.detail) from exc


def _row_json(value: str, *, field: str) -> dict[str, Any]:
    try:
        return v5_control._loads(value)
    except v5_control.ControlPlaneError as exc:
        raise RegistryEpochControlError(exc.code, f"{field}: {exc.detail}") from exc


def _preselection_context(
    conn: sqlite3.Connection, bundle: dict[str, Any],
) -> tuple[sqlite3.Row, dict[str, Any], sqlite3.Row, dict[str, Any]]:
    provenance = bundle.get("source_provenance")
    if not isinstance(provenance, dict):
        raise RegistryEpochControlError("source_provenance_missing", "registry epoch requires H1/H2 source provenance")
    h1 = provenance.get("h1")
    h2 = provenance.get("h2")
    if not isinstance(h1, dict) or not isinstance(h2, dict):
        raise RegistryEpochControlError("source_provenance_invalid", "registry epoch requires H1 and H2 receipt snapshots")
    h1_id = _required_text(h1, "receipt_id")
    h1_version = _positive_integer(h1.get("receipt_version"), field="source_provenance.h1.receipt_version")
    h2_id = _required_text(h2, "receipt_id")
    h2_version = _positive_integer(h2.get("receipt_version"), field="source_provenance.h2.receipt_version")
    try:
        h1_row = v5_control._preselection_row(
            conn, h1_id, h1_version, expected_kind=v5_control.H1_STATIC_COHORT_RECEIPT,
        )
        h2_row = v5_control._preselection_row(
            conn, h2_id, h2_version, expected_kind=v5_control.H2_ACTION_SCREEN_RECEIPT,
        )
    except v5_control.ControlPlaneError as exc:
        raise RegistryEpochControlError(exc.code, exc.detail) from exc
    if (h2_row["parent_receipt_id"], h2_row["parent_receipt_version"]) != (h1_id, h1_version):
        raise RegistryEpochControlError("source_provenance_parent_mismatch", "H2 receipt must be parented by the declared H1 receipt")
    if (
        h1.get("cohort_id") != h1_row["cohort_id"]
        or h1.get("curator_id") != h1_row["curator_id"]
        or _parse_time(h1.get("selection_as_of"), field="source_provenance.h1.selection_as_of")
        != _parse_time(h1_row["selection_as_of"], field="registered_h1.selection_as_of")
    ):
        raise RegistryEpochControlError("source_provenance_h1_snapshot_mismatch", "H1 snapshot does not match its registered receipt")
    if (
        h2.get("parent_receipt_id") != h2_row["parent_receipt_id"]
        or h2.get("parent_receipt_version") != h2_row["parent_receipt_version"]
        or h2.get("screen_id") != h2_row["screen_id"]
        or _parse_time(h2.get("cutoff_at"), field="source_provenance.h2.cutoff_at")
        != _parse_time(h2_row["cutoff_at"], field="registered_h2.cutoff_at")
    ):
        raise RegistryEpochControlError("source_provenance_h2_snapshot_mismatch", "H2 snapshot does not match its registered receipt")
    return h1_row, _row_json(h1_row["payload_json"], field="registered_h1"), h2_row, _row_json(h2_row["payload_json"], field="registered_h2")


def _registry_context(
    conn: sqlite3.Connection,
    bundle: dict[str, Any],
    binding: dict[str, Any],
    *,
    h1_row: sqlite3.Row,
    h2_row: sqlite3.Row,
) -> tuple[sqlite3.Row, dict[str, Any], list[sqlite3.Row]]:
    registry_id = _required_text(binding, "registry_id")
    try:
        registry_row = historical_control._registry_row(conn, registry_id)
    except historical_control.HistoricalTrainingControlError as exc:
        raise RegistryEpochControlError(exc.code, exc.detail) from exc
    if (registry_row["h1_receipt_id"], registry_row["h1_receipt_version"]) != (
        h1_row["receipt_id"], h1_row["receipt_version"],
    ):
        raise RegistryEpochControlError("registry_epoch_h1_parent_mismatch", "registry must have been created from the bundle H1 receipt")
    registry = _row_json(registry_row["registry_json"], field="carrier_registry")
    if registry_row["registry_state"] != "OPEN" or registry.get("state") != "OPEN":
        raise RegistryEpochControlError("registry_epoch_registry_not_open", "registry must be open until this seal atomically closes it")
    predicate = registry.get("peer_recruitment_predicate")
    if not isinstance(predicate, dict):
        raise RegistryEpochControlError("registry_epoch_predicate_missing", "registry requires a previously recorded recruitment predicate")
    action_ref = predicate.get("action_screen_receipt_ref")
    if not isinstance(action_ref, dict) or (
        action_ref.get("receipt_id"), action_ref.get("receipt_version")
    ) != (h2_row["receipt_id"], h2_row["receipt_version"]):
        raise RegistryEpochControlError("registry_epoch_h2_binding_mismatch", "registry predicate must reference the bundle H2 receipt")
    if _parse_time(predicate.get("source_cutoff_at"), field="registry.predicate.source_cutoff_at") != _parse_time(
        h2_row["cutoff_at"], field="registered_h2.cutoff_at",
    ):
        raise RegistryEpochControlError("registry_epoch_cutoff_mismatch", "registry predicate cutoff must equal H2 cutoff")
    action = bundle.get("action_scope")
    arena = bundle.get("competitive_arena")
    if not isinstance(action, dict) or registry.get("mechanism_topology") != action.get("mechanism_topology"):
        raise RegistryEpochControlError("registry_epoch_topology_mismatch", "registry topology must equal the V5 action topology")
    if not isinstance(arena, dict) or not isinstance(arena.get("competitive_arena_id"), str):
        raise RegistryEpochControlError("registry_epoch_arena_missing", "V5 root requires a competitive arena identity")
    time_contract = bundle.get("time_contract")
    if not isinstance(time_contract, dict) or _parse_time(
        time_contract.get("research_cutoff_at"), field="time_contract.research_cutoff_at",
    ) != _parse_time(h2_row["cutoff_at"], field="registered_h2.cutoff_at"):
        raise RegistryEpochControlError("registry_epoch_root_cutoff_mismatch", "V5 root cutoff must equal the registered H2 cutoff")
    event_rows = conn.execute(
        f"SELECT * FROM {historical_control.EVENT_TABLE} WHERE registry_id = ? ORDER BY sequence_number",
        (registry_id,),
    ).fetchall()
    actual_sequence = event_rows[-1]["sequence_number"] if event_rows else 0
    if binding.get("preseal_registry_event_sequence") != actual_sequence:
        raise RegistryEpochControlError("registry_epoch_preseal_sequence_mismatch", "binding does not name the current persisted registry event sequence")
    if any(item.get("disposition") == "PENDING_ACTION_WINDOW_REVIEW" for item in registry.get("carriers", [])):
        raise RegistryEpochControlError("registry_epoch_pending_carrier", "every registry carrier must be resolved before comparative seal")
    batch_rows = conn.execute(
        f"SELECT * FROM {historical_control.BATCH_RECEIPT_TABLE} WHERE registry_id = ? ORDER BY batch_id",
        (registry_id,),
    ).fetchall()
    return registry_row, registry, batch_rows


def _canonical_batch_source(source: dict[str, Any]) -> dict[str, Any]:
    published_at = source.get("published_at")
    if not isinstance(published_at, str) or not published_at.strip():
        raise RegistryEpochControlError("registry_batch_source_invalid", "registered static peer source lacks publication time")
    return {
        "source_id": source.get("source_id"),
        "official_artifact_id": source.get("source_id"),
        "source_url": source.get("url"),
        "publisher": v5_control.STATIC_CNINFO_PUBLISHER,
        "source_type": source.get("source_type"),
        "issuer_id": source.get("issuer_id"),
        "responsibility_unit_id": source.get("responsibility_unit_id"),
        "perimeter_id": source.get("perimeter_id"),
        "unit": source.get("unit"),
        "published_at_or_date": published_at,
        "availability_precision": v5_control._static_availability_precision(published_at),
        "outcome_visibility": "PREOUTCOME_VISIBLE",
        "permitted_lanes": {"STAGE0_STATIC", "PUBLIC_ARENA_CONTEXT"},
        "period_end": source.get("period_end"),
    }


def _registry_static_source_map(
    h1_payload: dict[str, Any], h2_payload: dict[str, Any], batch_rows: list[sqlite3.Row],
) -> dict[str, dict[str, Any]]:
    try:
        source_map = v5_control._preselection_static_source_map(h1_payload, h2_payload)
    except v5_control.ControlPlaneError as exc:
        raise RegistryEpochControlError(exc.code, exc.detail) from exc
    for row in batch_rows:
        batch = _row_json(row["payload_json"], field="registered_static_peer_batch")
        for raw in batch.get("static_sources", []):
            if not isinstance(raw, dict):
                raise RegistryEpochControlError("registry_batch_source_invalid", "registered static peer batch source must be an object")
            source = _canonical_batch_source(raw)
            source_id = source.get("source_id")
            if not isinstance(source_id, str) or not source_id.strip():
                raise RegistryEpochControlError("registry_batch_source_invalid", "registered static peer batch source_id is required")
            existing = source_map.get(source_id)
            if existing is not None:
                raise RegistryEpochControlError("registry_batch_source_id_redeclared", "static peer batch cannot redeclare an H1/H2 source ID")
            source_map[source_id] = source
    return source_map


def _registry_batch_coverage(batch_rows: list[sqlite3.Row]) -> dict[str, set[tuple[str, str, str]]]:
    """Reconstruct the immutable per-carrier field coverage from batch receipts."""
    coverage: dict[str, set[tuple[str, str, str]]] = {}
    for row in batch_rows:
        batch = _row_json(row["payload_json"], field="registered_static_peer_batch")
        for raw in batch.get("carrier_static_coverage", []):
            if not isinstance(raw, dict):  # pragma: no cover - controlled writer invariant
                raise RegistryEpochControlError("registry_batch_coverage_invalid", "registered batch coverage must be an object")
            carrier_id = raw.get("carrier_id")
            period_end = raw.get("period_end")
            field_id = raw.get("field_id")
            source_id = raw.get("source_id")
            if not all(isinstance(item, str) and item.strip() for item in (carrier_id, period_end, field_id, source_id)):
                raise RegistryEpochControlError("registry_batch_coverage_invalid", "registered batch coverage lacks a carrier, period, field, or source identity")
            coverage.setdefault(carrier_id, set()).add((period_end, field_id, source_id))
    return coverage


def _require_manifest_matches_registry(bundle: dict[str, Any], source_map: dict[str, dict[str, Any]]) -> None:
    manifest = bundle.get("source_manifest")
    if not isinstance(manifest, list):
        raise RegistryEpochControlError("source_manifest_identity_invalid", "V5 source_manifest must be a list")
    for item in manifest:
        if not isinstance(item, dict):
            raise RegistryEpochControlError("source_manifest_identity_invalid", "V5 source_manifest entries must be objects")
        source_id = item.get("source_id")
        source = source_map.get(source_id) if isinstance(source_id, str) else None
        if source is None:
            raise RegistryEpochControlError("source_manifest_outside_registered_registry_map", "source manifest references a source outside persisted H1/H2/batch receipts")
        mismatches = [
            field for field in v5_control._STATIC_SOURCE_IDENTITY_FIELDS
            if item.get(field) != source.get(field)
        ]
        if mismatches:
            raise RegistryEpochControlError("source_manifest_identity_mismatch", "source manifest differs from its persisted static PDF: " + ", ".join(mismatches))
        if item.get("source_lane") not in source["permitted_lanes"]:
            raise RegistryEpochControlError("source_manifest_lane_not_authorized", "source lane is not authorized by its persisted receipt")


def _require_registry_panel_projection(
    bundle: dict[str, Any],
    binding: dict[str, Any],
    registry: dict[str, Any],
    h1_payload: dict[str, Any],
    h2_payload: dict[str, Any],
    source_map: dict[str, dict[str, Any]],
    batch_coverage: dict[str, set[tuple[str, str, str]]],
) -> None:
    carriers = registry.get("carriers")
    if not isinstance(carriers, list):
        raise RegistryEpochControlError("registry_epoch_carriers_invalid", "persisted registry carriers must be a list")
    carrier_by_id = {
        item.get("carrier_id"): item for item in carriers
        if isinstance(item, dict) and isinstance(item.get("carrier_id"), str) and item["carrier_id"].strip()
    }
    ledger = binding.get("registry_panel_disposition_ledger")
    if not isinstance(ledger, list):
        raise RegistryEpochControlError("registry_epoch_ledger_invalid", "binding requires a carrier disposition ledger")
    ledger_by_id = {item.get("carrier_id"): item for item in ledger if isinstance(item, dict)}
    if set(ledger_by_id) != set(carrier_by_id) or len(ledger_by_id) != len(ledger):
        raise RegistryEpochControlError("registry_epoch_ledger_must_cover_all_carriers", "binding ledger must account for every persisted carrier exactly once")
    arena = bundle.get("competitive_arena")
    arena_bridge = binding.get("registry_selection_arena_bridge")
    if not isinstance(arena, dict) or not isinstance(arena_bridge, dict) or (
        arena_bridge.get("registry_competitive_arena_id"), arena_bridge.get("selection_competitive_arena_id"),
        arena_bridge.get("relation"),
    ) != (registry.get("competitive_arena_id"), arena.get("competitive_arena_id"), "MECHANISM_COMPATIBLE"):
        raise RegistryEpochControlError("registry_epoch_arena_bridge_mismatch", "binding must source-bind the registry and selection arena identities")
    if any(source_id not in source_map for source_id in arena_bridge.get("source_ids", [])):
        raise RegistryEpochControlError("registry_epoch_arena_bridge_source_not_registered", "arena bridge must cite persisted static sources")
    target_id = binding["target_carrier_id"]
    panel_ids = binding["ordered_panel_carrier_ids"]
    selected_ids = [target_id, *panel_ids]
    for carrier_id in selected_ids:
        carrier = carrier_by_id.get(carrier_id)
        if carrier is None or carrier.get("disposition") != "ELIGIBLE_FOR_COMPARATIVE":
            raise RegistryEpochControlError("registry_epoch_panel_carrier_not_eligible", "target/panel carrier must be persistently eligible")
        if carrier.get("seed_disposition") == "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK":
            raise RegistryEpochControlError("registry_epoch_break_carrier_forbidden", "known scope/control break cannot enter the comparative panel")
    if ledger_by_id[target_id].get("panel_disposition") != "TARGET" or any(
        ledger_by_id[carrier_id].get("panel_disposition") != "EXTERNAL_SHOCK_COMPARATOR" for carrier_id in panel_ids
    ):
        raise RegistryEpochControlError("registry_epoch_ledger_panel_mismatch", "binding ledger must match its target and ordered panel")
    for carrier_id, item in ledger_by_id.items():
        if carrier_id not in selected_ids and item.get("panel_disposition") != "EXCLUDED_PREOUTCOME":
            raise RegistryEpochControlError("registry_epoch_ledger_exclusion_mismatch", "every non-panel carrier must have a pre-outcome exclusion")
        for source_id in item.get("source_ids", []):
            source = source_map.get(source_id)
            if source is None:
                raise RegistryEpochControlError("registry_epoch_ledger_source_not_registered", "ledger reasoning must cite a persisted static source")
            if source.get("issuer_id") not in {carrier_by_id[carrier_id].get("issuer_id"), None} \
                    and item.get("panel_disposition") != "EXCLUDED_PREOUTCOME":
                raise RegistryEpochControlError("registry_epoch_ledger_source_identity_mismatch", "included carrier reasoning must cite its own persisted source")

    cohort = bundle.get("cohort_snapshot")
    if not isinstance(cohort, dict) or not isinstance(cohort.get("members"), list):
        raise RegistryEpochControlError("registry_epoch_cohort_missing", "V5 root must carry a cohort member projection")
    members = cohort["members"]
    by_issuer = {item.get("issuer_id"): item for item in members if isinstance(item, dict)}
    selected_issuers = {carrier_by_id[carrier_id]["issuer_id"] for carrier_id in selected_ids}
    if set(by_issuer) != selected_issuers or len(by_issuer) != len(members):
        raise RegistryEpochControlError("registry_epoch_cohort_must_exactly_match_panel", "root cohort must be exactly the binding target plus external comparators")
    action = bundle.get("action_scope")
    if not isinstance(action, dict) or action.get("focal_issuer_id") != carrier_by_id[target_id]["issuer_id"]:
        raise RegistryEpochControlError("registry_epoch_target_action_mismatch", "binding target must be the V5 focal issuer")
    panel = bundle.get("counterfactual_panel")
    if not isinstance(panel, dict) or panel.get("target_issuer_id") != carrier_by_id[target_id]["issuer_id"]:
        raise RegistryEpochControlError("registry_epoch_target_panel_mismatch", "binding target must be the counterfactual target")
    external_issuers = [
        item.get("issuer_id") for item in panel.get("members", []) if isinstance(item, dict)
        and item.get("causal_role") == "EXTERNAL_SHOCK_COMPARATOR"
    ]
    if external_issuers != [carrier_by_id[carrier_id]["issuer_id"] for carrier_id in panel_ids]:
        raise RegistryEpochControlError("registry_epoch_panel_order_mismatch", "V5 external comparator order must equal the binding order")

    h1_issuers = {
        item.get("issuer_id") for item in h1_payload.get("members", [])
        if isinstance(item, dict) and isinstance(item.get("issuer_id"), str)
    }
    h1_members = [item for item in members if item.get("issuer_id") in h1_issuers]
    if h1_members:
        probe = deepcopy(bundle)
        probe["cohort_snapshot"] = {**cohort, "members": h1_members}
        try:
            v5_control._require_h1_cohort_projection(
                probe, h1_payload, v5_control._preselection_static_source_map(h1_payload, h2_payload),
            )
        except v5_control.ControlPlaneError as exc:
            raise RegistryEpochControlError(exc.code, exc.detail) from exc
    for carrier_id in selected_ids:
        carrier = carrier_by_id[carrier_id]
        member = by_issuer[carrier["issuer_id"]]
        for field in ("company_id", "issuer_id", "responsibility_unit_id", "control_group_id"):
            if member.get(field) != carrier.get(field):
                raise RegistryEpochControlError("registry_epoch_member_identity_mismatch", "V5 cohort member differs from persisted carrier identity")
        boundary = member.get("boundary")
        if not isinstance(boundary, dict) or any(boundary.get(field) != carrier.get(field) for field in ("responsibility_unit_id", "perimeter_id", "unit")):
            raise RegistryEpochControlError("registry_epoch_member_boundary_mismatch", "V5 cohort member differs from persisted carrier boundary")
        if carrier.get("issuer_id") in h1_issuers:
            continue
        allowed_sources = set(carrier.get("static_source_ids") or [])
        immutable_coverage = batch_coverage.get(carrier_id, set())
        if not immutable_coverage:
            raise RegistryEpochControlError("registry_epoch_recruited_field_coverage_missing", "recruited carrier lacks immutable field coverage")
        for source_id in member.get("carrier_identity_source_ids", []):
            if source_id not in allowed_sources:
                raise RegistryEpochControlError("registry_epoch_recruited_carrier_source_mismatch", "recruited carrier identity source is not in its immutable batch")
        for history_name in ("d2_or_cost_field_history", "d3_d4_field_history"):
            for record in member.get(history_name, []):
                if not isinstance(record, dict) or record.get("source_id") not in allowed_sources:
                    raise RegistryEpochControlError("registry_epoch_recruited_field_source_mismatch", "recruited field history must use its immutable batch source")
                source = source_map.get(record["source_id"])
                if source is None or source.get("issuer_id") != carrier.get("issuer_id") or source.get("period_end") != record.get("period_end"):
                    raise RegistryEpochControlError("registry_epoch_recruited_field_period_or_issuer_mismatch", "recruited field history must match source issuer and fiscal period")
                if (record.get("period_end"), record.get("field_id"), record.get("source_id")) not in immutable_coverage:
                    raise RegistryEpochControlError("registry_epoch_recruited_field_coverage_mismatch", "recruited field history must exactly match immutable batch coverage")


def _insert_freeze(conn: sqlite3.Connection, bundle: dict[str, Any]) -> dict[str, Any]:
    freeze_id = _required_text(bundle, "selection_freeze_id")
    candidate_id = _required_text(bundle, "candidate_id")
    collision_key = _required_text(bundle, "episode_collision_key")
    time_contract = bundle.get("time_contract")
    if not isinstance(time_contract, dict):
        raise RegistryEpochControlError("time_contract_missing", "selection bundle requires time_contract")
    cutoff = _required_text(time_contract, "research_cutoff_at")
    _parse_time(cutoff, field="research_cutoff_at")
    sealed_at = v5_control._iso(_parse_time(bundle.get("sealed_at"), field="sealed_at"))
    recorded_at = v5_control._iso(_parse_time(bundle.get("recorded_at"), field="recorded_at"))
    predecessor = bundle.get("predecessor_freeze_id")
    if predecessor is not None and (not isinstance(predecessor, str) or not predecessor.strip()):
        raise RegistryEpochControlError("predecessor_invalid", "predecessor_freeze_id must be non-empty when present")
    predecessor = predecessor.strip() if isinstance(predecessor, str) else None
    bundle_json = v5_control._json(bundle)
    existing = conn.execute(
        f"SELECT * FROM {v5_control.FREEZE_TABLE} WHERE selection_freeze_id = ?", (freeze_id,),
    ).fetchone()
    if existing is not None:
        if existing["bundle_json"] != bundle_json:
            raise RegistryEpochControlError("freeze_immutable_conflict", "selection_freeze_id already has a different bundle")
        return {"selection_freeze_id": freeze_id, "idempotent": True}
    same_collision = conn.execute(
        f"SELECT selection_freeze_id FROM {v5_control.FREEZE_TABLE} WHERE episode_collision_key = ?", (collision_key,),
    ).fetchall()
    if same_collision:
        if predecessor is None:
            raise RegistryEpochControlError("collision_predecessor_required", "same collision key requires a voided predecessor")
        try:
            predecessor_row = v5_control._freeze_row(conn, predecessor)
            if predecessor_row["episode_collision_key"] != collision_key:
                raise RegistryEpochControlError("collision_predecessor_mismatch", "predecessor must use the same collision key")
            if v5_control._state(conn, predecessor)["terminal_state"] != "FREEZE_VOIDED_PRE_ACCESS":
                raise RegistryEpochControlError("collision_reuse_forbidden", "collision may be reused only after pre-access void")
            for row in same_collision:
                if v5_control._state(conn, row["selection_freeze_id"])["terminal_state"] != "FREEZE_VOIDED_PRE_ACCESS":
                    raise RegistryEpochControlError("collision_reuse_forbidden", "collision already has a non-voided freeze")
        except v5_control.ControlPlaneError as exc:
            raise RegistryEpochControlError(exc.code, exc.detail) from exc
    elif predecessor is not None:
        raise RegistryEpochControlError("predecessor_without_collision", "predecessor requires an existing collision")
    conn.execute(
        f"""INSERT INTO {v5_control.FREEZE_TABLE} (
            selection_freeze_id, candidate_id, episode_collision_key,
            research_cutoff_at, predecessor_freeze_id, bundle_json,
            sealed_at, recorded_at, schema_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (freeze_id, candidate_id, collision_key, cutoff, predecessor, bundle_json,
         sealed_at, recorded_at, v5_control.SCHEMA_VERSION),
    )
    return {"selection_freeze_id": freeze_id, "idempotent": False}


def seal_registry_aware_v5_freeze(
    conn: sqlite3.Connection,
    bundle: dict[str, Any],
    binding: dict[str, Any],
    *,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Atomically close a persisted registry and seal one unchanged V5 root."""
    validation = epoch.validate_registry_aware_v5_binding(bundle, binding)
    if not validation["valid"]:
        return {"sealed": False, "admission_status": validation["admission_status"], "findings": validation["findings"]}
    binding_json = v5_control._json(binding)
    existing_binding = conn.execute(
        f"SELECT * FROM {BINDING_TABLE} WHERE selection_freeze_id = ?", (bundle["selection_freeze_id"],),
    ).fetchone()
    if existing_binding is not None:
        freeze = conn.execute(
            f"SELECT bundle_json FROM {v5_control.FREEZE_TABLE} WHERE selection_freeze_id = ?",
            (bundle["selection_freeze_id"],),
        ).fetchone()
        if existing_binding["binding_json"] != binding_json or freeze is None or freeze["bundle_json"] != v5_control._json(bundle):
            raise RegistryEpochControlError("registry_epoch_binding_immutable_conflict", "selection freeze already has a different registry binding or root")
        return {"sealed": True, "selection_freeze_id": bundle["selection_freeze_id"], "idempotent": True}
    existing_binding_id = conn.execute(
        f"SELECT selection_freeze_id FROM {BINDING_TABLE} WHERE binding_id = ?", (binding["binding_id"],),
    ).fetchone()
    if existing_binding_id is not None:
        raise RegistryEpochControlError(
            "registry_epoch_binding_id_conflict",
            "binding_id already belongs to a different immutable selection freeze",
        )
    if recorded_at is not None and _parse_time(recorded_at, field="recorded_at") != _parse_time(
        bundle.get("recorded_at"), field="bundle.recorded_at",
    ):
        raise RegistryEpochControlError("recorded_at_mismatch", "recorded_at must equal the canonical V5 root value")
    try:
        v5_control._forbid_pre_access_outcome_identity(bundle, field="selection bundle")
        v5_control._forbid_pre_access_outcome_identity(binding, field="registry binding")
    except v5_control.ControlPlaneError as exc:
        raise RegistryEpochControlError(exc.code, exc.detail) from exc
    h1_row, h1_payload, h2_row, h2_payload = _preselection_context(conn, bundle)
    registry_row, registry, batch_rows = _registry_context(
        conn, bundle, binding, h1_row=h1_row, h2_row=h2_row,
    )
    source_map = _registry_static_source_map(h1_payload, h2_payload, batch_rows)
    batch_coverage = _registry_batch_coverage(batch_rows)
    _require_manifest_matches_registry(bundle, source_map)
    _require_registry_panel_projection(
        bundle, binding, registry, h1_payload, h2_payload, source_map, batch_coverage,
    )
    freeze_result = history.freeze_evidence_carrier_registry(registry, frozen_at=bundle["recorded_at"])
    if not freeze_result["valid"]:
        raise RegistryEpochControlError("registry_epoch_registry_freeze_invalid", "; ".join(freeze_result["findings"]))
    canonical_recorded = v5_control._iso(_parse_time(bundle["recorded_at"], field="bundle.recorded_at"))
    with conn:
        inserted = _insert_freeze(conn, bundle)
        if inserted["idempotent"]:
            existing = conn.execute(
                f"SELECT binding_json FROM {BINDING_TABLE} WHERE selection_freeze_id = ?",
                (bundle["selection_freeze_id"],),
            ).fetchone()
            if existing is not None and existing["binding_json"] == binding_json:
                return {"sealed": True, "selection_freeze_id": bundle["selection_freeze_id"], "idempotent": True}
            if existing is not None:
                raise RegistryEpochControlError(
                    "registry_epoch_binding_immutable_conflict",
                    "selection freeze already has a different registry binding",
                )
            raise RegistryEpochControlError("registry_epoch_binding_missing_for_existing_freeze", "existing legacy freeze cannot be retrofitted with a registry binding")
        try:
            historical_control._save_registry(
                conn, registry_row, freeze_result["carrier_registry"], event_kind="CARRIER_REGISTRY_FROZEN_FOR_V5_EPOCH",
                payload={"binding_id": binding["binding_id"], "selection_freeze_id": bundle["selection_freeze_id"]},
                recorded_at=canonical_recorded,
            )
        except historical_control.HistoricalTrainingControlError as exc:
            raise RegistryEpochControlError(exc.code, exc.detail) from exc
        try:
            conn.execute(
                f"""INSERT INTO {BINDING_TABLE} (
                    selection_freeze_id, binding_id, registry_id, preseal_registry_event_sequence,
                    binding_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (bundle["selection_freeze_id"], binding["binding_id"], binding["registry_id"],
                 binding["preseal_registry_event_sequence"], binding_json, canonical_recorded),
            )
        except sqlite3.IntegrityError as exc:
            raise RegistryEpochControlError(
                "registry_epoch_binding_id_conflict",
                "binding_id already belongs to a different immutable selection freeze",
            ) from exc
    return {"sealed": True, "selection_freeze_id": bundle["selection_freeze_id"], "idempotent": False}


def load_registry_epoch_binding(conn: sqlite3.Connection, selection_freeze_id: str) -> dict[str, Any]:
    row = conn.execute(
        f"SELECT * FROM {BINDING_TABLE} WHERE selection_freeze_id = ?", (selection_freeze_id,),
    ).fetchone()
    if row is None:
        raise RegistryEpochControlError("registry_epoch_binding_not_found", "selection freeze has no registry-epoch binding")
    return {
        "schema_version": SCHEMA_VERSION,
        "selection_freeze_id": selection_freeze_id,
        "binding": _row_json(row["binding_json"], field="registry_epoch_binding"),
        "recorded_at": row["recorded_at"],
    }
