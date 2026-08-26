#!/usr/bin/env python3
"""Canonical shared registry for immutable training selection inputs.

This is a small control-plane registry, not a settlement engine.  It stores
the immutable roster bundle and formal completion/adjudication receipts in the
shared canonical database so production selection can resolve identities by
ID instead of trusting caller-supplied JSON or paths.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

try:
    from scripts import enterprise_judgment_reconstruction as reconstruction
except ModuleNotFoundError:  # pragma: no cover
    import enterprise_judgment_reconstruction as reconstruction


SCHEMA_VERSION = "enterprise-judgment-training-control-plane.v1"
ROSTER_TABLE = "enterprise_judgment_training_roster_freezes"
RECEIPT_TABLE = "enterprise_judgment_training_selection_receipts"
MEASUREMENT_CONTRACT_TABLE = "enterprise_judgment_training_measurement_contracts"
ROSTER_OBJECT_CLASS = "ENTERPRISE_JUDGMENT_PRE_OUTCOME_FREEZE"
RECEIPT_SCHEMAS = {
    "enterprise-judgment-feedback-settlement.v1",
    "enterprise-judgment-continuation-feedback-settlement.v1",
    "enterprise-judgment-round3-feedback-settlement.v1",
    "enterprise-mechanism-feedback-superseding-adjudication.v1",
}


class TrainingControlPlaneError(ValueError):
    """A canonical training input cannot be registered or resolved."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load(value: str, *, code: str) -> dict[str, Any]:
    try:
        item = json.loads(value)
    except json.JSONDecodeError as exc:
        raise TrainingControlPlaneError(code, "stored payload is not valid JSON") from exc
    if not isinstance(item, dict):
        raise TrainingControlPlaneError(code, "stored payload must be an object")
    return item


def _instant(value: Any, *, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise TrainingControlPlaneError(f"{field}_invalid", f"{field} must be timezone-aware ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TrainingControlPlaneError(f"{field}_invalid", f"{field} must be timezone-aware ISO-8601")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _ref(value: Any, *, field: str) -> tuple[str, int]:
    if not isinstance(value, dict) or not isinstance(value.get("receipt_id"), str) or not value["receipt_id"].strip():
        raise TrainingControlPlaneError(f"{field}_invalid", f"{field}.receipt_id is required")
    if set(value) != {"receipt_id", "receipt_version"}:
        raise TrainingControlPlaneError(f"{field}_invalid", f"{field} accepts receipt identity only")
    version = value.get("receipt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise TrainingControlPlaneError(f"{field}_invalid", f"{field}.receipt_version must be a positive integer")
    return value["receipt_id"], version


def _canonical_conn(*, readonly: bool = False) -> sqlite3.Connection:
    path = reconstruction.CANONICAL_REGISTRY_PATH.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if readonly:
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except sqlite3.OperationalError as exc:
            raise TrainingControlPlaneError("canonical_control_plane_unavailable", str(exc)) from exc
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    with conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {ROSTER_TABLE} (
                freeze_id TEXT PRIMARY KEY,
                block_id TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {RECEIPT_TABLE} (
                receipt_id TEXT NOT NULL,
                receipt_version INTEGER NOT NULL,
                schema_version TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                freeze_id TEXT,
                block_id TEXT,
                company_id TEXT,
                transition_id TEXT,
                PRIMARY KEY (receipt_id, receipt_version)
            )"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {MEASUREMENT_CONTRACT_TABLE} (
                contract_set_id TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL,
                company_id TEXT NOT NULL,
                cutoff_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                frozen_at TEXT NOT NULL
            )"""
        )
        receipt_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({RECEIPT_TABLE})")}
        for column in ("freeze_id", "block_id", "company_id", "transition_id"):
            if column not in receipt_columns:
                conn.execute(f"ALTER TABLE {RECEIPT_TABLE} ADD COLUMN {column} TEXT")


def _validate_roster_bundle(bundle: Any) -> dict[str, Any]:
    item = bundle if isinstance(bundle, dict) else {}
    block = item.get("block") if isinstance(item.get("block"), dict) else {}
    freeze = item.get("roster_freeze") if isinstance(item.get("roster_freeze"), dict) else {}
    if freeze.get("schema_version") != "enterprise-judgment-pre-outcome-freeze.v1":
        raise TrainingControlPlaneError("roster_freeze_schema_invalid", "canonical roster must be the formal immutable freeze")
    if freeze.get("object_class") != ROSTER_OBJECT_CLASS or freeze.get("claim_class") != "ROSTER_IMMUTABILITY_BINDING":
        raise TrainingControlPlaneError("roster_freeze_identity_invalid", "canonical roster identity is invalid")
    freeze_id = freeze.get("freeze_id")
    block_id = freeze.get("block_id")
    rows = block.get("company_cutoff_transition_roster")
    ids = freeze.get("company_cutoff_transition_ids")
    if not isinstance(freeze_id, str) or not freeze_id or not isinstance(block_id, str) or not block_id:
        raise TrainingControlPlaneError("roster_freeze_identity_missing", "freeze_id and block_id are required")
    if not isinstance(rows, list) or not rows or not isinstance(ids, list) or [row.get("transition_id") for row in rows] != ids:
        raise TrainingControlPlaneError("roster_freeze_order_invalid", "canonical roster must preserve the immutable row order")
    if [row.get("rank") for row in rows] != list(range(1, len(rows) + 1)):
        raise TrainingControlPlaneError("roster_freeze_rank_invalid", "canonical roster ranks must be contiguous")
    return {"freeze_id": freeze_id, "block_id": block_id, "block": deepcopy(block), "roster_freeze": deepcopy(freeze)}


def register_roster_freeze(bundle: dict[str, Any], *, registered_at: str) -> dict[str, Any]:
    """Register the exact block + immutable freeze bundle in shared storage."""
    canonical = _validate_roster_bundle(bundle)
    timestamp = _instant(registered_at, field="registered_at")
    conn = _canonical_conn()
    try:
        initialize(conn)
        encoded = _json(canonical)
        existing = conn.execute(
            f"SELECT payload_json, registered_at FROM {ROSTER_TABLE} WHERE freeze_id = ?",
            (canonical["freeze_id"],),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["registered_at"] != timestamp:
                raise TrainingControlPlaneError("roster_freeze_identity_conflict", "registered roster identity has different content")
            return {"registered": True, "freeze_id": canonical["freeze_id"], "idempotent": True}
        conflict = conn.execute(f"SELECT freeze_id FROM {ROSTER_TABLE} WHERE block_id = ?", (canonical["block_id"],)).fetchone()
        if conflict is not None:
            raise TrainingControlPlaneError("block_has_different_registered_roster", "one block cannot have two canonical roster freezes")
        with conn:
            conn.execute(
                f"INSERT INTO {ROSTER_TABLE} (freeze_id, block_id, payload_json, registered_at) VALUES (?, ?, ?, ?)",
                (canonical["freeze_id"], canonical["block_id"], encoded, timestamp),
            )
        return {"registered": True, "freeze_id": canonical["freeze_id"], "idempotent": False}
    finally:
        conn.close()


def _receipt_identity(receipt: dict[str, Any]) -> tuple[str, int]:
    schema = receipt.get("schema_version")
    if schema not in RECEIPT_SCHEMAS:
        raise TrainingControlPlaneError("receipt_schema_unsupported", "only formal completion/adjudication receipts may be registered")
    if schema == "enterprise-mechanism-feedback-superseding-adjudication.v1":
        receipt_id, version = receipt.get("adjudication_id"), 1
    else:
        receipt_id, version = receipt.get("settlement_id"), 1
    if not isinstance(receipt_id, str) or not receipt_id:
        raise TrainingControlPlaneError("receipt_identity_missing", "formal receipt identity is missing")
    return receipt_id, version


def _receipt_validation_and_binding(
    receipt: dict[str, Any], *, bundle: dict[str, Any], validation_context: dict[str, Any],
) -> dict[str, Any]:
    try:
        from scripts import enterprise_judgment_real_mechanism_training as real_training
        from scripts import enterprise_judgment_v2_training as v2
    except ModuleNotFoundError:  # pragma: no cover
        import enterprise_judgment_real_mechanism_training as real_training
        import enterprise_judgment_v2_training as v2
    block = bundle["block"]
    freeze = bundle["roster_freeze"]
    context = validation_context if isinstance(validation_context, dict) else {}
    schema = receipt.get("schema_version")
    common = {
        "block": block,
        "pre_outcome_roster_freeze": freeze,
        "history_series": context.get("history_series"),
        "h1_package": context.get("h1_package"),
        "source_block_episodes": context.get("source_block_episodes"),
        "source_models": context.get("source_models"),
    }
    if schema == "enterprise-judgment-feedback-settlement.v1":
        validation = v2.validate_feedback_settlement(
            receipt,
            block=block,
            pre_outcome_roster_freeze=freeze,
            history_series=context.get("history_series"),
            h1_package=context.get("h1_package"),
            episodes=context.get("source_block_episodes"),
            enterprise_models=context.get("source_models"),
        )
    elif schema == "enterprise-judgment-continuation-feedback-settlement.v1":
        validation = v2.validate_continuation_feedback_settlement(
            receipt,
            application=context.get("round2_application"),
            selection=context.get("round2_selection"),
            eligibility_register=context.get("round2_eligibility_register"),
            target_episode=context.get("round2_target_episode"),
            target_models=context.get("round2_target_models"),
            source_feedback_settlement=context.get("source_feedback_settlement"),
            completed_feedback_settlements=context.get("completed_feedback_settlements"),
            **common,
        )
    elif schema == "enterprise-judgment-round3-feedback-settlement.v1":
        validation = v2.validate_round3_feedback_settlement(
            receipt,
            application=context.get("round3_application"),
            selection=context.get("round3_selection"),
            round2_chain=context.get("round2_chain"),
            target_episode=context.get("round3_target_episode"),
            target_models=context.get("round3_target_models"),
            completed_feedback_settlements=context.get("completed_feedback_settlements"),
            **common,
        )
    elif schema == "enterprise-mechanism-feedback-superseding-adjudication.v1":
        validation = real_training.validate_superseding_adjudication(
            receipt, block=block, roster_freeze=freeze,
        )
    else:  # guarded by _receipt_identity
        raise TrainingControlPlaneError("receipt_schema_unsupported", "no production validator for receipt schema")
    if not validation["valid"]:
        raise TrainingControlPlaneError(
            "selection_receipt_production_validation_failed", "; ".join(validation["findings"]),
        )
    roster = bundle["block"]["company_cutoff_transition_roster"]
    if schema == "enterprise-mechanism-feedback-superseding-adjudication.v1":
        transition_id = receipt["supersedes"]["transition_id"]
        matches = [row for row in roster if row.get("transition_id") == transition_id]
    else:
        matches = [
            row for row in roster
            if row.get("company_id") == receipt.get("company_id") and row.get("cutoff_at") == receipt.get("cutoff_at")
        ]
    if len(matches) != 1:
        raise TrainingControlPlaneError(
            "selection_receipt_roster_binding_not_unique",
            "validated receipt must bind exactly one immutable company-cutoff transition",
        )
    transition = matches[0]
    return {
        "freeze_id": freeze["freeze_id"],
        "block_id": block["block_id"],
        "company_id": transition["company_id"],
        "transition_id": transition["transition_id"],
    }


def register_selection_receipt(
    receipt: dict[str, Any], *, roster_freeze_ref: dict[str, Any], validation_context: dict[str, Any], registered_at: str,
) -> dict[str, Any]:
    receipt_id, version = _receipt_identity(receipt)
    timestamp = _instant(registered_at, field="registered_at")
    encoded = _json(receipt)
    bundle, _ = resolve_canonical_selection_inputs(roster_freeze_ref, [])
    binding = _receipt_validation_and_binding(
        receipt, bundle=bundle, validation_context=validation_context,
    )
    conn = _canonical_conn()
    try:
        initialize(conn)
        existing = conn.execute(
            f"""SELECT payload_json, schema_version, registered_at, freeze_id, block_id, company_id, transition_id
                FROM {RECEIPT_TABLE} WHERE receipt_id = ? AND receipt_version = ?""",
            (receipt_id, version),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["schema_version"] != receipt["schema_version"] or existing["registered_at"] != timestamp:
                raise TrainingControlPlaneError("selection_receipt_identity_conflict", "registered receipt identity has different content")
            stored_binding = {key: existing[key] for key in binding}
            if any(stored_binding.values()) and stored_binding != binding:
                raise TrainingControlPlaneError("selection_receipt_binding_conflict", "registered receipt has a different immutable roster binding")
            if stored_binding != binding:
                with conn:
                    conn.execute(
                        f"""UPDATE {RECEIPT_TABLE}
                            SET freeze_id = ?, block_id = ?, company_id = ?, transition_id = ?
                            WHERE receipt_id = ? AND receipt_version = ?""",
                        (*binding.values(), receipt_id, version),
                    )
            return {
                "registered": True, "receipt_id": receipt_id, "receipt_version": version,
                "idempotent": True, "binding": binding,
            }
        with conn:
            conn.execute(
                f"""INSERT INTO {RECEIPT_TABLE}
                    (receipt_id, receipt_version, schema_version, payload_json, registered_at, freeze_id, block_id, company_id, transition_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (receipt_id, version, receipt["schema_version"], encoded, timestamp, *binding.values()),
            )
        return {
            "registered": True, "receipt_id": receipt_id, "receipt_version": version,
            "idempotent": False, "binding": binding,
        }
    finally:
        conn.close()


def resolve_canonical_selection_inputs(
    roster_freeze_ref: dict[str, Any], receipt_refs: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Resolve only registered IDs from the shared read-only control plane."""
    freeze_id = roster_freeze_ref.get("freeze_id") if isinstance(roster_freeze_ref, dict) else None
    if not isinstance(freeze_id, str) or not freeze_id or set(roster_freeze_ref) != {"freeze_id"}:
        raise TrainingControlPlaneError("roster_freeze_ref_invalid", "production selection requires freeze_id only")
    if not isinstance(receipt_refs, list) or any(not isinstance(ref, dict) for ref in receipt_refs):
        raise TrainingControlPlaneError("receipt_refs_invalid", "production selection requires receipt references, not payloads")
    conn = _canonical_conn(readonly=True)
    try:
        row = conn.execute(f"SELECT payload_json FROM {ROSTER_TABLE} WHERE freeze_id = ?", (freeze_id,)).fetchone()
        if row is None:
            raise TrainingControlPlaneError("roster_freeze_not_registered", "requested roster freeze is not canonical")
        bundle = _load(row["payload_json"], code="canonical_roster_payload_invalid")
        roster_by_id = {
            item.get("transition_id"): item
            for item in bundle["block"]["company_cutoff_transition_roster"]
        }
        resolved: list[dict[str, Any]] = []
        for index, ref in enumerate(receipt_refs):
            receipt_id, version = _ref(ref, field=f"receipt_refs[{index}]")
            receipt_row = conn.execute(
                f"""SELECT payload_json, freeze_id, block_id, company_id, transition_id
                    FROM {RECEIPT_TABLE} WHERE receipt_id = ? AND receipt_version = ?""",
                (receipt_id, version),
            ).fetchone()
            if receipt_row is None:
                raise TrainingControlPlaneError("selection_receipt_not_registered", f"receipt {receipt_id}@{version} is not canonical")
            transition = roster_by_id.get(receipt_row["transition_id"])
            if (
                receipt_row["freeze_id"] != freeze_id
                or receipt_row["block_id"] != bundle["block"]["block_id"]
                or not isinstance(transition, dict)
                or transition.get("company_id") != receipt_row["company_id"]
            ):
                raise TrainingControlPlaneError(
                    "selection_receipt_canonical_binding_invalid",
                    f"receipt {receipt_id}@{version} lacks a valid immutable roster binding",
                )
            resolved.append(_load(receipt_row["payload_json"], code="canonical_receipt_payload_invalid"))
        return bundle, resolved
    finally:
        conn.close()


def register_measurement_contract(contract: dict[str, Any], *, frozen_at: str) -> dict[str, Any]:
    """Freeze a validated v3 contract; the same ID can never be mutated."""
    try:
        from scripts import enterprise_judgment_real_mechanism_training as training
    except ModuleNotFoundError:  # pragma: no cover
        import enterprise_judgment_real_mechanism_training as training
    validation = training.validate_outcome_measurement_contract(contract)
    if not validation["valid"] or contract.get("schema_version") != training.CONTRACT_SCHEMA_VERSION_V3:
        raise TrainingControlPlaneError(
            "measurement_contract_invalid",
            "; ".join(validation["findings"] or ["only v3 contracts may enter this registry"]),
        )
    timestamp = _instant(frozen_at, field="frozen_at")
    if contract.get("contract_frozen_at") != timestamp:
        raise TrainingControlPlaneError("measurement_contract_freeze_time_mismatch", "payload freeze time must equal registry freeze time")
    encoded = _json(contract)
    contract_id = contract["contract_set_id"]
    conn = _canonical_conn()
    try:
        initialize(conn)
        existing = conn.execute(
            f"SELECT payload_json, frozen_at FROM {MEASUREMENT_CONTRACT_TABLE} WHERE contract_set_id = ?",
            (contract_id,),
        ).fetchone()
        if existing is not None:
            if existing["payload_json"] != encoded or existing["frozen_at"] != timestamp:
                raise TrainingControlPlaneError(
                    "measurement_contract_post_freeze_mutation",
                    "registered measurement contract identity cannot be changed after pre-outcome freeze",
                )
            return {"registered": True, "contract_set_id": contract_id, "idempotent": True}
        with conn:
            conn.execute(
                f"""INSERT INTO {MEASUREMENT_CONTRACT_TABLE}
                    (contract_set_id, schema_version, company_id, cutoff_at, payload_json, frozen_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                (contract_id, contract["schema_version"], contract["company_id"], contract["cutoff_at"], encoded, timestamp),
            )
        return {"registered": True, "contract_set_id": contract_id, "idempotent": False}
    finally:
        conn.close()


def resolve_measurement_contract(contract_set_id: str) -> dict[str, Any]:
    if not isinstance(contract_set_id, str) or not contract_set_id:
        raise TrainingControlPlaneError("measurement_contract_ref_invalid", "contract_set_id is required")
    conn = _canonical_conn(readonly=True)
    try:
        row = conn.execute(
            f"SELECT payload_json FROM {MEASUREMENT_CONTRACT_TABLE} WHERE contract_set_id = ?",
            (contract_set_id,),
        ).fetchone()
        if row is None:
            raise TrainingControlPlaneError("measurement_contract_not_registered", "measurement contract is not canonical")
        return _load(row["payload_json"], code="canonical_measurement_contract_payload_invalid")
    finally:
        conn.close()


def canonical_control_plane_path() -> str:
    return str(reconstruction.CANONICAL_REGISTRY_PATH.resolve())
